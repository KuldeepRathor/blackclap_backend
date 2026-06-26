from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.auth import get_current_user
from app.modules.posts.schemas import CreatePostRequest, FeedPostResponse, PostResponse
from app.modules.posts.service import create_post, get_feed_posts, get_user_posts, get_saved_posts_feed
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


@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post_endpoint(
    req: CreatePostRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PostResponse:
    return await create_post(user_id=current_user.id, req=req, db=db)
