from datetime import timedelta
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from supportops.constants import RoleEnum

from supportops.auth import (
    create_access_token,
    verify_password,
    get_current_user
)
from supportops.database import get_db
import supportops.models as models
from supportops.schemas import Token, UserResponse

router = APIRouter()


# ----------------- 1. Login / Token -----------------
@router.post("/token", response_model=Token, summary="Login and obtain access token")
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not form_data.username or not form_data.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Allow login by username OR email
    result = await db.execute(
        select(models.User)
        .options(selectinload(models.User.role))
        .where(
            or_(
                models.User.username == form_data.username,
                models.User.email == form_data.username,
            )
        )
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your account is not active. Please contact your manager or admin.",
        )

    role_name = user.role.name.lower() if user.role else RoleEnum.USER.value

    access_token = create_access_token(
        data={"sub": str(user.id), "role": role_name},
        expires_delta=timedelta(minutes=30),
    )
    return Token(access_token=access_token, token_type="bearer")


# ----------------- 2. Current User (/me) -----------------
@router.get("/me", response_model=UserResponse, summary="Get current logged in user")
async def get_current_user_route(
    current_user: Annotated[models.User, Depends(get_current_user)]
):
    return current_user