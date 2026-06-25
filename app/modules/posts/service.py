import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.comments.models import Comment
from app.modules.likes.models import PostLike
from app.modules.posts.models import Post, PostMedia
from app.modules.posts.schemas import CreatePostRequest, PostMediaResponse, PostResponse
from app.modules.saves.models import PostSave


def _build_post_response(
    post: Post,
    likes_count: int = 0,
    comments_count: int = 0,
    is_liked: bool = False,
    is_saved: bool = False,
) -> PostResponse:
    return PostResponse(
        id=post.id,
        user_id=post.user_id,
        caption=post.caption,
        location=post.location,
        media_type=post.media_type,
        media=[PostMediaResponse.model_validate(m) for m in post.media],
        likes_count=likes_count,
        comments_count=comments_count,
        is_liked=is_liked,
        is_saved=is_saved,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


async def _enrich_posts(
    posts: list[Post],
    requesting_user_id: uuid.UUID,
    db: AsyncSession,
) -> list[PostResponse]:
    if not posts:
        return []

    post_ids = [p.id for p in posts]

    likes_rows = await db.execute(
        select(PostLike.post_id, func.count().label("cnt"))
        .where(PostLike.post_id.in_(post_ids))
        .group_by(PostLike.post_id)
    )
    likes_map: dict[uuid.UUID, int] = {row.post_id: row.cnt for row in likes_rows}

    comments_rows = await db.execute(
        select(Comment.post_id, func.count().label("cnt"))
        .where(Comment.post_id.in_(post_ids), Comment.parent_id.is_(None))
        .group_by(Comment.post_id)
    )
    comments_map: dict[uuid.UUID, int] = {row.post_id: row.cnt for row in comments_rows}

    liked_rows = await db.execute(
        select(PostLike.post_id).where(
            PostLike.post_id.in_(post_ids),
            PostLike.user_id == requesting_user_id,
        )
    )
    liked_set: set[uuid.UUID] = {row.post_id for row in liked_rows}

    saved_rows = await db.execute(
        select(PostSave.post_id).where(
            PostSave.post_id.in_(post_ids),
            PostSave.user_id == requesting_user_id,
        )
    )
    saved_set: set[uuid.UUID] = {row.post_id for row in saved_rows}

    return [
        _build_post_response(
            post,
            likes_count=likes_map.get(post.id, 0),
            comments_count=comments_map.get(post.id, 0),
            is_liked=post.id in liked_set,
            is_saved=post.id in saved_set,
        )
        for post in posts
    ]


async def get_user_posts(
    user_id: uuid.UUID,
    requesting_user_id: uuid.UUID,
    db: AsyncSession,
) -> list[PostResponse]:
    stmt = (
        select(Post)
        .where(Post.user_id == user_id)
        .options(selectinload(Post.media))
        .order_by(Post.created_at.desc())
    )
    result = await db.execute(stmt)
    posts = list(result.scalars().all())
    return await _enrich_posts(posts, requesting_user_id, db)


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

    return _build_post_response(post)
