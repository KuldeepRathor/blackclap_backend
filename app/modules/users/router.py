import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.auth import get_current_user
from app.core.security.jwt import decode_access_token
from app.modules.follows.models import Follow
from app.modules.posts.models import Post
from app.modules.users.models import User
from app.modules.users.schemas import UserProfileResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["Users"])

_oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/token", auto_error=False
)


async def _get_optional_user(
    token: Optional[str] = Depends(_oauth2_scheme_optional),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    user_id_str: Optional[str] = payload.get("sub")
    if not user_id_str:
        return None
    try:
        result = await db.execute(select(User).where(User.id == uuid.UUID(user_id_str)))
        return result.scalar_one_or_none()
    except ValueError:
        return None


async def _build_profile_response(
    user: User,
    db: AsyncSession,
    requesting_user_id: Optional[uuid.UUID] = None,
) -> UserProfileResponse:
    posts_count = (
        await db.scalar(
            select(func.count(Post.id)).where(
                Post.user_id == user.id, Post.deleted_at.is_(None)
            )
        )
        or 0
    )
    followers_count = (
        await db.scalar(
            select(func.count(Follow.id)).where(Follow.followed_id == user.id)
        )
        or 0
    )
    following_count = (
        await db.scalar(
            select(func.count(Follow.id)).where(Follow.follower_id == user.id)
        )
        or 0
    )

    is_following = False
    if requesting_user_id and requesting_user_id != user.id:
        row = await db.execute(
            select(Follow).where(
                Follow.follower_id == requesting_user_id,
                Follow.followed_id == user.id,
            )
        )
        is_following = row.scalar_one_or_none() is not None

    return UserProfileResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        bio=user.bio,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        posts_count=posts_count,
        followers_count=followers_count,
        following_count=following_count,
        is_following=is_following,
    )


@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Retrieve detailed profile information of the currently authenticated user."""
    return await _build_profile_response(
        current_user, db, requesting_user_id=current_user.id
    )


@router.patch("/me", response_model=UserProfileResponse)
async def update_my_profile(
    user_in: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Update the authenticated user's profile details."""
    update_data = user_in.model_dump(exclude_unset=True)

    if not update_data:
        return await _build_profile_response(
            current_user, db, requesting_user_id=current_user.id
        )

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

    for field, value in update_data.items():
        setattr(current_user, field, value)

    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)

    return await _build_profile_response(
        current_user, db, requesting_user_id=current_user.id
    )


@router.delete("/me", status_code=status.HTTP_200_OK)
async def delete_my_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Soft-delete the authenticated user's account (in-app deletion).

    Deactivates immediately (all authenticated access stops) and starts the
    grace period; logging back in within it restores the account, otherwise the
    scheduled purge permanently removes/anonymizes the data. Mirrors the public
    web flow in the `account` module.
    """
    current_user.is_active = False
    current_user.deleted_at = datetime.now(timezone.utc)
    db.add(current_user)
    await db.commit()
    return {"detail": "Your account has been scheduled for deletion."}


@router.get("/{username}", response_model=UserProfileResponse)
async def get_public_profile(
    username: str,
    db: AsyncSession = Depends(get_db),
    requesting_user: Optional[User] = Depends(_get_optional_user),
) -> Any:
    """Retrieve the public profile of another user by their username."""
    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User account is inactive"
        )

    requesting_user_id = requesting_user.id if requesting_user else None
    return await _build_profile_response(
        user, db, requesting_user_id=requesting_user_id
    )
