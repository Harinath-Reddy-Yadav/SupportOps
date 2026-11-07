from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select
from typing import Annotated
from supportops import models
from supportops.database import get_db
from supportops.schemas import UserResponse, UserPublicResponse, UserPrivateCreate, UserCreate, UserPrivateUpdate, UserUpdate

router = APIRouter()

#Create new user with default roile has customer
@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user: UserCreate,
    db: Annotated[Session, Depends(get_db)]
    ):
    #Validate email and user name already exists
    if validate_username_and_email_valid(user, db):
        #Create user
        new_user = models.User(**user.dict())
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    return new_user
    
    


#Create new user with specified role by admin or by user itself
@router.post("/admin", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user_admin(
    user: UserPrivateCreate,
    db: Annotated[Session, Depends(get_db)]
):
    #Validate email and user name already exists
    if validate_username_and_email_valid(user, db):
        #Create user
        new_user = models.User(**user.dict())
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    return new_user


#update user
@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user: UserUpdate,
    db: Annotated[Session, Depends(get_db)]
):
    valid_update = validate_user_update(user_id, user, db)
    if valid_update:
        existing_user = db.execute(select(models.User).where(models.User.id == user_id)).scalar_one_or_none()
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        existing_user.email = user.email
        existing_user.username = user.username
        existing_user.password = user.password
        existing_user.first_name = user.first_name
        existing_user.last_name = user.last_name
        db.commit()
        db.refresh(existing_user)
    return existing_user


#update user role by admin
@router.put("/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: int,
    user: UserPrivateUpdate,
    db: Annotated[Session, Depends(get_db)]
):
    existing_user = db.execute(select(models.User).where(models.User.id == user_id)).scalar_one_or_none()
    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    if validate_username_and_email_valid(user, db):
        existing_user.role = user.role
        db.commit()
        db.refresh(existing_user)
    return existing_user


#Get the current user
@router.get("/me", response_model=UserResponse)
def get_current_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)]
):
    current_user = db.execute(select(models.User).where(models.User.id == user_id)).scalar_one_or_none()
    return current_user


#Get all the users only for admins
@router.get("/admin/users", response_model=list[UserResponse])
def get_all_users(
    db: Annotated[Session, Depends(get_db)]
):
    all_users = db.execute(select(models.User)).scalars().all()
    return all_users


#Delete the user
@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)]
):
    existing_user = db.execute(select(models.User).where(models.User.id == user_id)).scalar_one_or_none()
    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    db.delete(existing_user)
    db.commit()
    return {"message": "User deleted successfully"}


## ---------------------------------------------- Helper functions -----------------------------------------------------------------##
#Duplicate username and email validation
def validate_username_and_email_valid(user: UserCreate, db: Annotated[Session, Depends(get_db)]) -> bool:
    email_user = db.execute(select(models.User).where(models.User.email == user.email)).scalar_one_or_none()
    if email_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists"
        )
    user_name = db.execute(select(models.User).where(models.User.username == user.username)).scalar_one_or_none()
    if user_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User name already exists"
        )
    return True

#userid validation
def validate_user_update(user_id: int, user: UserUpdate, db: Annotated[Session, Depends(get_db)]):
    # Check if another user has this email
    if user.email:
        email_user = db.execute(
            select(models.User).where(
                models.User.email == user.email, 
                models.User.id != user_id
            )
        ).scalar_one_or_none()
        if email_user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already taken")

    # Check if another user has this username
    if user.username:
        username_user = db.execute(
            select(models.User).where(
                models.User.username == user.username, 
                models.User.id != user_id
            )
        ).scalar_one_or_none()
        if username_user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken")