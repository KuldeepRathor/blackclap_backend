import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.likes.models import PostLike
from app.modules.likes.schemas import LikeResponse
from app.modules.notifications.dispatch import enqueue_push
from app.modules.posts.models import Post
from app.modules.users.models import User


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

    # Notify the post owner of a new like (never on unlike, never self-like).
    if is_liked and post.user_id != user_id:
        actor = await db.get(User, user_id)
        actor_name = (actor.display_name or actor.username) if actor else "Someone"
        enqueue_push(
            recipient_id=post.user_id,
            title=actor_name,
            body="liked your post",
            data={"type": "like", "post_id": str(post_id)},
        )

    likes_count = await db.scalar(
        select(func.count()).where(PostLike.post_id == post_id)
    )

    return LikeResponse(
        post_id=post_id, likes_count=likes_count or 0, is_liked=is_liked
    )
