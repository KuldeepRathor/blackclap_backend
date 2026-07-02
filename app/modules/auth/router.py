from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.auth import get_current_user
from app.core.security.jwt import create_access_token, create_refresh_token
from app.core.security.password import hash_password, verify_password
from app.modules.account.service import is_within_grace_period, reactivate_account
from app.modules.auth.schemas import (
    AuthResponse,
    Token,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.modules.users.models import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED
)
async def register(user_in: UserRegister, db: AsyncSession = Depends(get_db)) -> Any:
    """
    Register a new user in the system.
    Validates username/email uniqueness, hashes the password, and creates the record.
    Returns the user profile along with access and refresh tokens.
    """
    # Check if user with same email or username already exists
    stmt = select(User).where(
        or_(User.email == user_in.email, User.username == user_in.username)
    )
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        if existing_user.email == user_in.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email already exists.",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this username already exists.",
            )

    # Hash the password and create the user object
    hashed = hash_password(user_in.password)
    user = User(
        email=user_in.email,
        username=user_in.username,
        hashed_password=hashed,
        display_name=user_in.username,  # default display name is username
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Automatically generate access & refresh tokens on signup
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user,
    }


@router.post("/login", response_model=AuthResponse)
async def login(user_in: UserLogin, db: AsyncSession = Depends(get_db)) -> Any:
    """
    Login using email or username and password, returning an access and refresh token.
    Accepts JSON body.
    """
    # Find user by username or email
    stmt = select(User).where(
        or_(
            User.username == user_in.email_or_username,
            User.email == user_in.email_or_username,
        )
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect username/email or password",
        )

    if not user.is_active:
        # A soft-deleted account can be recovered by logging in within the grace
        # period; otherwise it stays locked (pending permanent deletion).
        if is_within_grace_period(user):
            await reactivate_account(db, user)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User account is inactive",
            )

    # Generate JWT tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user,
    }


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    OAuth2 compatible token login, returning an access token and a refresh token.
    Allows authentication using either Username or Email in the username field.
    """
    # Find user by username or email
    stmt = select(User).where(
        or_(
            User.username == form_data.username,
            User.email == form_data.username,
        )
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect username/email or password",
        )

    if not user.is_active:
        # Reactivate a soft-deleted account on login within the grace period.
        if is_within_grace_period(user):
            await reactivate_account(db, user)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User account is inactive",
            )

    # Generate JWT tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> Any:
    """Get profile information of the currently authenticated user."""
    return current_user
