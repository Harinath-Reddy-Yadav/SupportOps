from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Annotated
from supportops import models
from supportops.database import get_db
from supportops.schemas import (
    UserResponse, UserPrivateCreate, UserCreate,
    UserRoleUpdate, UserUpdate
)

router = APIRouter()


# ----------------- 1. Create User (Default Customer Role) -----------------
@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="Create new customer user")
async def create_user(
    user: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    await validate_username_and_email_valid(user.username, user.email, db)
    new_user = models.User(**user.model_dump())
    new_user.role_id = 1
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


# ----------------- 2. Create user by Specific Role (Admin or Manager) -----------------
@router.post("/admin", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="Create user with custom role by admin")
@router.post("/manager", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="Create user with custom role by manager")
async def create_user_admin(
    user: UserPrivateCreate,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    await validate_username_and_email_valid(user.username, user.email, db)
    
    if user.role_id is not None:
        role = await db.get(models.Role, user.role_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Specified role_id does not exist")

    new_user = models.User(**user.model_dump())
    if new_user.role_id is None:
        new_user.role_id = 1
    if Request.url.path.endswith("/manager"):
        new_user.manager_id = user.id
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


# ----------------- 3. Current User -----------------
@router.get("/me", response_model=UserResponse, summary="Get current logged in user")
async def get_current_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    current_user = await db.get(models.User, user_id)
    if not current_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return current_user


# ----------------- 4. Get All users by admin -----------------
@router.get("/admin/users", response_model=list[UserResponse], summary="Get all users by admin")
async def get_all_users(
    db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(select(models.User).order_by(models.User.id))
    return result.scalars().all()


# ----------------- 4. Dynamic Parameterized routes -----------------
@router.get("/{user_id}", response_model=UserResponse, summary="Get user by ID")
async def get_user_by_id(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    user = await db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.put("/{user_id}", response_model=UserResponse, summary="Update user details")
async def update_user(
    user_id: int,
    user: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    existing_user = await db.get(models.User, user_id)
    if not existing_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await validate_user_update(user_id, user, db)

    for field, value in user.model_dump(exclude_unset=True).items():
        setattr(existing_user, field, value)

    try:
        await db.commit()
        await db.refresh(existing_user)
        return existing_user
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update user")


@router.put("/{user_id}/role", response_model=UserResponse, summary="Update user role")
async def update_user_role(
    user_id: int,
    user_role: UserRoleUpdate,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    existing_user = await db.get(models.User, user_id)
    if not existing_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user_role.role_id is not None:
        role = await db.get(models.Role, user_role.role_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role ID does not exist")
        existing_user.role_id = user_role.role_id

    try:
        await db.commit()
        await db.refresh(existing_user)
        return existing_user
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update user role")


@router.delete("/{user_id}", summary="Delete user")
async def delete_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    existing_user = await db.get(models.User, user_id)
    if not existing_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    try:
        await db.delete(existing_user)
        await db.commit()
        return {"message": "User deleted successfully"}
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete user with associated tickets/comments")


# ----------------- Helper functions -----------------
async def validate_username_and_email_valid(user: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]) -> bool:
    email_res = db.execute(select(models.User).where(models.User.email == user.email))
    email_user = email_res.scalar_one_or_none()
    if email_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists"
        )
    user_res = await db.execute(select(models.User).where(models.User.username == user.username))
    user_name = user_res.scalar_one_or_none()
    if user_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User name already exists"
        )
    return True


async def validate_user_update(user_id: int, user: UserUpdate, db: AsyncSession) -> bool:
    if user.email:
        email_res = await db.execute(
            select(models.User).where(models.User.email == user.email, models.User.id != user_id)
        )
        if email_res.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already taken")

    if user.username:
        user_res = await db.execute(
            select(models.User).where(models.User.username == user.username, models.User.id != user_id)
        )
        if user_res.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken")

    return True