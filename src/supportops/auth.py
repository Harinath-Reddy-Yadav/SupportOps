from datetime import UTC, datetime, timedelta
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from supportops.config import settings
from typing import Annotated
from fastapi import Depends, HTTPException, status
import supportops.models as models
from supportops.database import get_db
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
import jwt
import supportops.models as models
from supportops.constants import RoleEnum

password_hasher = PasswordHash.recommended()


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login/token")

#-----------------Hash Password -----------------------------------
def hash_password(password:str):
    return password_hasher.hash(password)

#-----------------Verify Password ---------------------------------
def verify_password(password:str,hashed_password:str):
    return password_hasher.verify(password,hashed_password)


#------------------ Create JWT Access Token ---------------------------
def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.SECRET_KEY.get_secret_value(), 
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt


#-------------- Verify JWT Access Token ---------------------------------
def decode_access_token(token: str) -> dict:
    try:
        secret = settings.SECRET_KEY.get_secret_value()
        payload = jwt.decode(
            token,
            secret,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please log in again."
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials."
        )


#------------------ Create current user dependency ---------------------------
async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db),
) -> models.User:
    payload = decode_access_token(token)
    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials."
        )
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials."
        )
    result = await db.execute(
        select(models.User)
        .options(selectinload(models.User.role))
        .options(selectinload(models.User.manager))
        .where(models.User.id == user_id)  # Fixed: .id
    )
    user = result.scalar_one_or_none()
    if user is None or user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your account is not active. Please contact your manager or system administrator.",
        )
    return user

class RequireRole:
    """Dependency that checks if the current user has one of the allowed roles."""
    def __init__(self, *allowed_roles: str):
        self.allowed_roles = [
            r.value.lower() if hasattr(r, "value") else str(r).lower() 
            for r in allowed_roles
        ]
    async def __call__(self, current_user: Annotated[models.User, Depends(get_current_user)]) -> models.User: #__call__ is inbuilt and used to make an object of a class callable for ex: obj()
        user_role = current_user.role.name.lower() if current_user.role else ""
        
        if user_role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Invalid Role '{user_role}'"
            )
        return current_user

# Reusable Role Type Aliases:
CurrentUser = Annotated[models.User, Depends(get_current_user)]
AdminUser = Annotated[models.User, Depends(RequireRole(RoleEnum.ADMIN.value))]
ManagerUser = Annotated[models.User, Depends(RequireRole(RoleEnum.ADMIN.value, RoleEnum.MANAGER.value))]
StaffUser = Annotated[models.User, Depends(RequireRole(RoleEnum.ADMIN.value, RoleEnum.MANAGER.value, RoleEnum.AGENT.value))]