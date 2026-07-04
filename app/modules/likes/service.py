import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.likes.models import PostLike
from app.modules.likes.schemas import LikeResponse
from app.modules.posts.models import Post


async def toggle_like(
    post_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> LikeResponse:
    post = await db.get(Post, post_id)
    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    existing = await db.scalar(
        select(PostLike).where(PostLike.post_id == post_id, PostLike.user_id == user_id)
    )

    if existing:
        await db.delete(existing)
        is_liked = False
    else:
        db.add(PostLike(post_id=post_id, user_id=user_id))
        is_liked = True

    await db.commit()

    likes_count = await db.scalar(
        select(func.count()).where(PostLike.post_id == post_id)
    )

    return LikeResponse(
        post_id=post_id, likes_count=likes_count or 0, is_liked=is_liked
    )
