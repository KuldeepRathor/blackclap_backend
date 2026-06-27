import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.auth import get_current_user
from app.modules.posts.models import Post
from app.modules.posts.schemas import CreatePostRequest, FeedPostResponse, PostResponse
from app.modules.posts.service import (
    create_post,
    get_feed_posts,
    get_reels,
    get_user_posts,
    get_saved_posts_feed,
    get_tagged_posts,
    record_post_view_bg,
)
from app.modules.users.models import User

router = APIRouter(prefix="/posts", tags=["Posts"])


@router.get("/feed", response_model=list[FeedPostResponse])
async def get_feed_endpoint(
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[FeedPostResponse]:
    return await get_feed_posts(
        requesting_user_id=current_user.id,
        db=db,
        limit=limit,
        offset=offset,
    )


@router.get("/reels", response_model=list[FeedPostResponse])
async def get_reels_endpoint(
    limit: int = Query(default=20, ge=1, le=50),
    cursor: datetime | None = Query(default=None, description="created_at of the last reel received; omit for first page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[FeedPostResponse]:
    return await get_reels(
        requesting_user_id=current_user.id,
        db=db,
        limit=limit,
        cursor=cursor,
    )


@router.get("/me", response_model=list[FeedPostResponse])
async def get_my_posts_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[FeedPostResponse]:
    return await get_user_posts(
        user_id=current_user.id,
        requesting_user_id=current_user.id,
        db=db,
    )


@router.get("/user/{username}", response_model=list[FeedPostResponse])
async def get_posts_by_username_endpoint(
    username: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[FeedPostResponse]:
    result = await db.execute(select(User).where(User.username == username))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return await get_user_posts(
        user_id=target.id,
        requesting_user_id=current_user.id,
        db=db,
    )


@router.get("/me/tagged", response_model=list[FeedPostResponse])
async def get_my_tagged_posts_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[FeedPostResponse]:
    return await get_tagged_posts(
        user_id=current_user.id,
        requesting_user_id=current_user.id,
        db=db,
    )


@router.get("/tagged/{username}", response_model=list[FeedPostResponse])
async def get_tagged_posts_by_username_endpoint(
    username: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[FeedPostResponse]:
    result = await db.execute(select(User).where(User.username == username))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return await get_tagged_posts(
        user_id=target.id,
        requesting_user_id=current_user.id,
        db=db,
    )


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post_endpoint(
    post_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    from datetime import datetime, timezone

    from sqlalchemy import update as sa_update

    result = await db.execute(
        select(Post).where(Post.id == post_id, Post.deleted_at.is_(None))
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")
    if post.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your post.")
    await db.execute(
        sa_update(Post)
        .where(Post.id == post_id)
        .values(deleted_at=datetime.now(timezone.utc))
    )
    await db.commit()


@router.post("/{post_id}/view", status_code=status.HTTP_204_NO_CONTENT)
async def record_view_endpoint(
    post_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
) -> None:
    # Returns immediately; DB write happens after response is sent
    background_tasks.add_task(record_post_view_bg, post_id, current_user.id)


@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post_endpoint(
    req: CreatePostRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PostResponse:
    return await create_post(user_id=current_user.id, req=req, db=db)
