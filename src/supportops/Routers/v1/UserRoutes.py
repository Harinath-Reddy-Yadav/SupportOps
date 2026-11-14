from ssl import CERT_REQUIRED
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
from supportops.auth import hash_password, CurrentUser, AdminUser, ManagerUser, StaffUser
from datetime import datetime, UTC
from sqlalchemy import update
router = APIRouter()


# ----------------- 1. Create User (Default Customer Role) -----------------
@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="Create new customer user")
async def create_user(
    user: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    await validate_username_and_email_valid(user.username, user.email, db)
    user_dict = user.model_dump()
    plain_password = user_dict.pop("password")
    new_user = models.User(**user_dict)
    new_user.password_hash = hash_password(plain_password)
    new_user.role_id = 1
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


# ----------------- 2. Create user by Specific Role (Admin or Manager) -----------------
@router.post("/admin", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="Create user with custom role by admin")
@router.post("/manager", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="Create user with custom role by manager")
async def create_user_admin(
    request: Request,
    user: UserPrivateCreate,
    current_user: ManagerUser,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    await validate_username_and_email_valid(user.username, user.email, db)
    
    if user.role_id is not None:
        role = await db.get(models.Role, user.role_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Specified role_id does not exist")
    
        # Security Rule: Managers cannot assign Admin role
        if current_user.role.name.lower() == "manager" and role.name.lower() == "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Managers are not allowed to create or assign Admin accounts. Please contact admin."
            )

    user_dict = user.model_dump()
    plain_password = user_dict.pop("password")
    new_user = models.User(**user_dict)
    new_user.password_hash = hash_password(plain_password)
    if new_user.role_id is None:
        new_user.role_id = 1
    if request.url.path.endswith("/manager"):
        new_user.manager_id = current_user.id
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


# ----------------- 4. Get All users by admin -----------------
@router.get("/admin/users", response_model=list[UserResponse], summary="Get all users by admin")
async def get_all_users(
    current_user: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(select(models.User).order_by(models.User.id))
    return result.scalars().all()

# ----------------- 4. Get All users assigned to manager -----------------
@router.get("/manager/users", response_model=list[UserResponse], summary="Get all users assigned to manager")
async def get_all_users_manager(
    current_user: ManagerUser,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(select(models.User).where(models.User.manager_id == current_user.id).order_by(models.User.id))
    return result.scalars().all()

# ----------------- 5. Get user by ID -----------------
@router.get("/{user_id}", response_model=UserResponse, summary="Get user by ID")
async def get_user_by_id(
    user_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    user = await db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

# ----------------- 6. Update user details -----------------
@router.put("/{user_id}", response_model=UserResponse, summary="Update user details")
async def update_user(
    user_id: int,
    user: UserUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    is_admin = current_user.role and current_user.role.name.lower() == "admin"
    if current_user.id != user_id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to update another user's profile"
        )
    existing_user = await db.get(models.User, user_id)
    if not existing_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await validate_user_update(user_id, user, db)
    update_dict = user.model_dump(exclude_unset=True)
    if "password" in update_dict:
        existing_user.password_hash = hash_password(update_dict.pop("password"))

    for field, value in update_dict.items():
        setattr(existing_user, field, value)

    try:
        await db.commit()
        await db.refresh(existing_user)
        return existing_user
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update user")


# ----------------- 6. Update user role by Manager or Admin-----------------
@router.put("/{user_id}/role", response_model=UserResponse, summary="Update user role")
async def update_user_role(
    user_id: int,
    user_role: UserRoleUpdate,
    current_user: ManagerUser,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    existing_user = await db.get(models.User, user_id)
    if not existing_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Security Rule: Managers cannot assign Admin role
        if current_user.role.name.lower() == "manager" and role.name.lower() == "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Managers are not allowed to create or assign Admin accounts. Please contact admin."
            )

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


# ----------------- 7. Soft Delete user by Manager or Admin -----------------
@router.delete("/{user_id}", summary="Delete user")
async def delete_user(
    user_id: int,
    current_user: ManagerUser,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    existing_user = await db.get(models.User, user_id)
    if not existing_user or existing_user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Security Rule: Managers cannot delete Admin accounts
    target_user_role = existing_user.role.name.lower() if existing_user.role else ""
    if current_user.role and current_user.role.name.lower() == "manager":
        if target_user_role == "admin" or target_user_role == "manager":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Managers are not allowed to delete Admin or Manager accounts."
            )

    # 1. Unassign tickets that were assigned to this user
    await db.execute(
        update(models.Ticket)
        .where(models.Ticket.assignee_id == user_id)
        .values(assignee_id=None)
    )

    # 2. Free up email & username for future re-registration and mark deleted
    existing_user.email = f"deleted_{existing_user.id}_{existing_user.email}"
    existing_user.username = f"deleted_{existing_user.id}_{existing_user.username}"
    existing_user.deleted_at = datetime.now(UTC)
    existing_user.is_active = False

    await db.commit()
    return {"message": "User deleted successfully"}


# ----------------- Helper functions -----------------
async def validate_username_and_email_valid(username: str, email: str, db: AsyncSession) -> bool:
    email_res = await db.execute(select(models.User).where(models.User.email == email))
    email_user = email_res.scalar_one_or_none()
    if email_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists"
        )
    user_res = await db.execute(select(models.User).where(models.User.username == username))
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