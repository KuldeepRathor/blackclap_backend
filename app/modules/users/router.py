from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.auth import get_current_user
from app.modules.users.models import User
from app.modules.users.schemas import UserProfileResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(current_user: User = Depends(get_current_user)) -> Any:
    """Retrieve detailed profile information of the currently authenticated user."""
    # Stats currently default to 0 as other tables are pending creation
    return current_user


@router.patch("/me", response_model=UserProfileResponse)
async def update_my_profile(
    user_in: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Update the authenticated user's profile details.
    Validates email/username uniqueness if modified.
    """
    update_data = user_in.model_dump(exclude_unset=True)

    if not update_data:
        return current_user

    # If updating username or email, ensure they are unique
    checks = []
    if "username" in update_data and update_data["username"] != current_user.username:
        checks.append(User.username == update_data["username"])
    if "email" in update_data and update_data["email"] != current_user.email:
        checks.append(User.email == update_data["email"])

    if checks:
        stmt = select(User).where(or_(*checks))
        result = await db.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            if (
                "username" in update_data
                and existing_user.username == update_data["username"]
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This username is already taken.",
                )
            if "email" in update_data and existing_user.email == update_data["email"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This email is already in use by another account.",
                )

    # Apply updates
    for field, value in update_data.items():
        setattr(current_user, field, value)

    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)

    return current_user


@router.get("/{username}", response_model=UserProfileResponse)
async def get_public_profile(username: str, db: AsyncSession = Depends(get_db)) -> Any:
    """Retrieve the public profile details of another user by their username."""
    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is inactive",
        )

    return user
