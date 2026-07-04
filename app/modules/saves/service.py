import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.posts.models import Post
from app.modules.saves.models import PostSave
from app.modules.saves.schemas import SaveResponse


async def toggle_save(
    post_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> SaveResponse:
    result = await db.execute(
        select(PostSave).where(
            PostSave.post_id == post_id,
            PostSave.user_id == user_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        await db.delete(existing)
        await db.commit()
        return SaveResponse(post_id=post_id, is_saved=False)

    db.add(PostSave(post_id=post_id, user_id=user_id))
    await db.commit()
    return SaveResponse(post_id=post_id, is_saved=True)


async def get_saved_posts(user_id: uuid.UUID, db: AsyncSession) -> list[Post]:
    result = await db.execute(
        select(Post)
        .join(PostSave, PostSave.post_id == Post.id)
        .where(PostSave.user_id == user_id)
        .options(selectinload(Post.media))
        .order_by(PostSave.created_at.desc())
    )
    return list(result.scalars().all())
