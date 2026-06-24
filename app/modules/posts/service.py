import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.posts.models import Post, PostMedia
from app.modules.posts.schemas import CreatePostRequest, PostResponse


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
