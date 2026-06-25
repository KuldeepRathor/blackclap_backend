import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.posts.models import Post, PostMedia
from app.modules.posts.schemas import CreatePostRequest, PostResponse


async def get_user_posts(user_id: uuid.UUID, db: AsyncSession) -> list[PostResponse]:
    stmt = (
        select(Post)
        .where(Post.user_id == user_id)
        .options(selectinload(Post.media))
        .order_by(Post.created_at.desc())
    )
    result = await db.execute(stmt)
    posts = result.scalars().all()
    return [PostResponse.model_validate(post) for post in posts]


async def create_post(
    user_id: uuid.UUID,
    req: CreatePostRequest,
    db: AsyncSession,
) -> PostResponse:
    post = Post(
        user_id=user_id,
        caption=req.caption,
        location=req.location,
        media_type=req.media_type.value,
    )
    db.add(post)
    await db.flush()

    for i, url in enumerate(req.media_urls):
        db.add(
            PostMedia(
                post_id=post.id,
                media_url=url,
                media_type=req.media_type.value,
                thumbnail_url=req.thumbnail_url if i == 0 else None,
                order=i,
            )
        )

    await db.commit()

    stmt = (
        select(Post)
        .where(Post.id == post.id)
        .options(selectinload(Post.media))
    )
    result = await db.execute(stmt)
    post = result.scalar_one()

    return PostResponse.model_validate(post)
