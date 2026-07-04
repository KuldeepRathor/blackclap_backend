import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.auth import get_current_user
from app.modules.follows.models import Follow
from app.modules.follows.schemas import FollowResponse
from app.modules.search.schemas import SearchUserResult
from app.modules.users.models import User

router = APIRouter(prefix="/follows", tags=["Follows"])


@router.post("/{username}", response_model=FollowResponse)
async def follow_user(
    username: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FollowResponse:
    """Follow another user by username."""
    target = await _get_target_user(username, current_user, db)

    existing = await db.execute(
        select(Follow).where(
            Follow.follower_id == current_user.id,
            Follow.followed_id == target.id,
        )
    )
    if existing.scalar_one_or_none() is None:
        db.add(Follow(follower_id=current_user.id, followed_id=target.id))
        await db.commit()

    return await _build_follow_response(current_user.id, target.id, db)


@router.delete("/{username}", response_model=FollowResponse)
async def unfollow_user(
    username: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FollowResponse:
    """Unfollow another user by username."""
    target = await _get_target_user(username, current_user, db)

    result = await db.execute(
        select(Follow).where(
            Follow.follower_id == current_user.id,
            Follow.followed_id == target.id,
        )
    )
    follow = result.scalar_one_or_none()
    if follow:
        await db.delete(follow)
        await db.commit()

    return await _build_follow_response(current_user.id, target.id, db)


@router.get("/{username}/followers", response_model=list[SearchUserResult])
async def get_followers(
    username: str,
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SearchUserResult]:
    """Users who follow `username`."""
    target = await _get_user_by_username(username, db)

    rows = await db.execute(
        select(User)
        .join(Follow, Follow.follower_id == User.id)
        .where(Follow.followed_id == target.id, User.deleted_at.is_(None))
        .order_by(Follow.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    users = list(rows.scalars().all())
    return await _enrich_with_is_following(users, current_user.id, db)


@router.get("/{username}/following", response_model=list[SearchUserResult])
async def get_following(
    username: str,
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SearchUserResult]:
    """Users that `username` follows."""
    target = await _get_user_by_username(username, db)

    rows = await db.execute(
        select(User)
        .join(Follow, Follow.followed_id == User.id)
        .where(Follow.follower_id == target.id, User.deleted_at.is_(None))
        .order_by(Follow.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    users = list(rows.scalars().all())
    return await _enrich_with_is_following(users, current_user.id, db)


async def _enrich_with_is_following(
    users: list[User],
    current_user_id: uuid.UUID,
    db: AsyncSession,
) -> list[SearchUserResult]:
    if not users:
        return []
    user_ids = [u.id for u in users]
    following_rows = await db.execute(
        select(Follow.followed_id).where(
            Follow.follower_id == current_user_id,
            Follow.followed_id.in_(user_ids),
        )
    )
    following_set = {row.followed_id for row in following_rows}
    return [
        SearchUserResult(
            id=u.id,
            username=u.username,
            display_name=u.display_name,
            avatar_url=u.avatar_url,
            bio=u.bio,
            is_following=u.id in following_set,
        )
        for u in users
    ]


async def _get_user_by_username(username: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )
    return user


async def _get_target_user(username: str, current_user: User, db: AsyncSession) -> User:
    if username == current_user.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot follow yourself.",
        )
    result = await db.execute(select(User).where(User.username == username))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )
    return target


async def _build_follow_response(
    current_user_id: uuid.UUID, target_user_id: uuid.UUID, db: AsyncSession
) -> FollowResponse:
    is_following_row = await db.execute(
        select(Follow).where(
            Follow.follower_id == current_user_id,
            Follow.followed_id == target_user_id,
        )
    )
    is_following = is_following_row.scalar_one_or_none() is not None

    followers_count = (
        await db.scalar(
            select(func.count(Follow.id)).where(Follow.followed_id == target_user_id)
        )
        or 0
    )
    following_count = (
        await db.scalar(
            select(func.count(Follow.id)).where(Follow.follower_id == target_user_id)
        )
        or 0
    )

    return FollowResponse(
        is_following=is_following,
        followers_count=followers_count,
        following_count=following_count,
    )
