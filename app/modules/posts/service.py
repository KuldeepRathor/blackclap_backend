import json
import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.comments.models import Comment
from app.modules.likes.models import PostLike
from app.modules.posts.models import Post, PostMedia, PostTag, PostView
from app.modules.posts.schemas import (
    CreatePostRequest,
    FeedPostResponse,
    MediaType,
    PostMediaResponse,
    PostResponse,
    TaggedUserResponse,
)
from app.modules.saves.models import PostSave
from app.modules.users.models import User

_REELS_CACHE_TTL = 60  # seconds — shared base data across all users


async def _fetch_tagged_users_map(
    post_ids: list[uuid.UUID],
    db: AsyncSession,
) -> dict[uuid.UUID, list[TaggedUserResponse]]:
    """Return a map of post_id → list of tagged user summaries."""
    if not post_ids:
        return {}

    tag_rows = await db.execute(
        select(PostTag.post_id, PostTag.tagged_user_id).where(
            PostTag.post_id.in_(post_ids), PostTag.deleted_at.is_(None)
        )
    )
    tag_pairs = [(row.post_id, row.tagged_user_id) for row in tag_rows]
    if not tag_pairs:
        return {}

    tagged_user_ids = list({uid for _, uid in tag_pairs})
    user_rows = await db.execute(
        select(User.id, User.username, User.display_name, User.avatar_url).where(
            User.id.in_(tagged_user_ids)
        )
    )
    users_map = {row.id: row for row in user_rows}

    result: dict[uuid.UUID, list[TaggedUserResponse]] = {}
    for post_id, tagged_user_id in tag_pairs:
        u = users_map.get(tagged_user_id)
        if u is None:
            continue
        result.setdefault(post_id, []).append(
            TaggedUserResponse(
                id=u.id,
                username=u.username,
                display_name=u.display_name,
                avatar_url=u.avatar_url,
            )
        )
    return result


def _build_post_response(
    post: Post,
    likes_count: int = 0,
    comments_count: int = 0,
    is_liked: bool = False,
    is_saved: bool = False,
    tagged_users: list[TaggedUserResponse] | None = None,
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
        views_count=post.views_count,
        is_liked=is_liked,
        is_saved=is_saved,
        tagged_users=tagged_users or [],
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


async def _enrich_posts_base(
    posts: list[Post],
    db: AsyncSession,
) -> list[FeedPostResponse]:
    """Enrich posts with non-user-specific data only (counts, author info, tags).
    is_liked and is_saved are left False — callers patch them per-user from cache."""
    if not posts:
        return []

    post_ids = [p.id for p in posts]
    user_ids = list({p.user_id for p in posts})

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

    users_rows = await db.execute(
        select(User.id, User.username, User.display_name, User.avatar_url).where(
            User.id.in_(user_ids)
        )
    )
    users_map = {row.id: row for row in users_rows}

    tags_map = await _fetch_tagged_users_map(post_ids, db)

    return [
        FeedPostResponse(
            id=post.id,
            user_id=post.user_id,
            caption=post.caption,
            location=post.location,
            media_type=post.media_type,
            media=[PostMediaResponse.model_validate(m) for m in post.media],
            likes_count=likes_map.get(post.id, 0),
            comments_count=comments_map.get(post.id, 0),
            views_count=post.views_count,
            is_liked=False,
            is_saved=False,
            tagged_users=tags_map.get(post.id, []),
            created_at=post.created_at,
            updated_at=post.updated_at,
            username=users_map[post.user_id].username
            if post.user_id in users_map
            else "",
            display_name=users_map[post.user_id].display_name
            if post.user_id in users_map
            else None,
            avatar_url=users_map[post.user_id].avatar_url
            if post.user_id in users_map
            else None,
        )
        for post in posts
    ]


async def _enrich_to_feed_responses(
    posts: list[Post],
    requesting_user_id: uuid.UUID,
    db: AsyncSession,
) -> list[FeedPostResponse]:
    """Enrich Post objects with counts, interaction flags, author info, and tags."""
    if not posts:
        return []

    post_ids = [p.id for p in posts]
    user_ids = list({p.user_id for p in posts})

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

    users_rows = await db.execute(
        select(User.id, User.username, User.display_name, User.avatar_url).where(
            User.id.in_(user_ids)
        )
    )
    users_map = {row.id: row for row in users_rows}

    tags_map = await _fetch_tagged_users_map(post_ids, db)

    return [
        FeedPostResponse(
            id=post.id,
            user_id=post.user_id,
            caption=post.caption,
            location=post.location,
            media_type=post.media_type,
            media=[PostMediaResponse.model_validate(m) for m in post.media],
            likes_count=likes_map.get(post.id, 0),
            comments_count=comments_map.get(post.id, 0),
            views_count=post.views_count,
            is_liked=post.id in liked_set,
            is_saved=post.id in saved_set,
            tagged_users=tags_map.get(post.id, []),
            created_at=post.created_at,
            updated_at=post.updated_at,
            username=users_map[post.user_id].username
            if post.user_id in users_map
            else "",
            display_name=users_map[post.user_id].display_name
            if post.user_id in users_map
            else None,
            avatar_url=users_map[post.user_id].avatar_url
            if post.user_id in users_map
            else None,
        )
        for post in posts
    ]


async def _enrich_posts(
    posts: list[Post],
    requesting_user_id: uuid.UUID,
    db: AsyncSession,
) -> list[PostResponse]:
    """Legacy enrichment — no author info. Kept for internal use only."""
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

    tags_map = await _fetch_tagged_users_map(post_ids, db)

    return [
        _build_post_response(
            post,
            likes_count=likes_map.get(post.id, 0),
            comments_count=comments_map.get(post.id, 0),
            is_liked=post.id in liked_set,
            is_saved=post.id in saved_set,
            tagged_users=tags_map.get(post.id, []),
        )
        for post in posts
    ]


async def get_user_posts(
    user_id: uuid.UUID,
    requesting_user_id: uuid.UUID,
    db: AsyncSession,
) -> list[FeedPostResponse]:
    stmt = (
        select(Post)
        .where(Post.user_id == user_id, Post.deleted_at.is_(None))
        .options(selectinload(Post.media))
        .order_by(Post.created_at.desc())
    )
    result = await db.execute(stmt)
    posts = list(result.scalars().all())
    return await _enrich_to_feed_responses(posts, requesting_user_id, db)


async def get_reels(
    requesting_user_id: uuid.UUID,
    db: AsyncSession,
    limit: int = 20,
    cursor: datetime | None = None,
) -> list[FeedPostResponse]:
    from app.core.cache.redis_cache import cache

    cursor_str = cursor.isoformat() if cursor else "start"
    cache_key = f"reels:base:{cursor_str}:{limit}"

    # Attempt to load shared base data from cache
    base_responses: list[FeedPostResponse] | None = None
    cached_raw = await cache.get(cache_key)
    if cached_raw is not None:
        try:
            base_responses = [
                FeedPostResponse.model_validate(d) for d in json.loads(cached_raw)
            ]
        except Exception:
            base_responses = None  # stale/corrupt — fall through to DB

    if base_responses is None:
        # Cursor-based query — avoids slow OFFSET scans
        stmt = (
            select(Post)
            .where(Post.deleted_at.is_(None), Post.media_type == "video")
            .options(selectinload(Post.media))
        )
        if cursor is not None:
            stmt = stmt.where(Post.created_at < cursor)
        stmt = stmt.order_by(Post.created_at.desc()).limit(limit)

        result = await db.execute(stmt)
        posts = list(result.scalars().all())

        base_responses = await _enrich_posts_base(posts, db)

        # Cache base data shared across all users (is_liked/is_saved excluded)
        await cache.setex(
            cache_key,
            _REELS_CACHE_TTL,
            json.dumps([r.model_dump(mode="json") for r in base_responses]),
        )

    if not base_responses:
        return base_responses

    # Apply user-specific flags — only 2 fast indexed queries
    post_ids = [r.id for r in base_responses]

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
        r.model_copy(
            update={"is_liked": r.id in liked_set, "is_saved": r.id in saved_set}
        )
        for r in base_responses
    ]


async def get_feed_posts(
    requesting_user_id: uuid.UUID,
    db: AsyncSession,
    limit: int = 20,
    offset: int = 0,
) -> list[FeedPostResponse]:
    stmt = (
        select(Post)
        .where(Post.deleted_at.is_(None))
        .options(selectinload(Post.media))
        .order_by(Post.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    posts = list(result.scalars().all())
    return await _enrich_to_feed_responses(posts, requesting_user_id, db)


async def get_saved_posts_feed(
    user_id: uuid.UUID,
    db: AsyncSession,
) -> list[FeedPostResponse]:
    """Return saved posts enriched with author info — same shape as feed."""
    result = await db.execute(
        select(Post)
        .join(PostSave, PostSave.post_id == Post.id)
        .where(PostSave.user_id == user_id, Post.deleted_at.is_(None))
        .options(selectinload(Post.media))
        .order_by(PostSave.created_at.desc())
    )
    posts = list(result.scalars().all())
    return await _enrich_to_feed_responses(posts, user_id, db)


async def get_tagged_posts(
    user_id: uuid.UUID,
    requesting_user_id: uuid.UUID,
    db: AsyncSession,
) -> list[FeedPostResponse]:
    """Return all posts where user_id has been tagged, newest first."""
    result = await db.execute(
        select(Post)
        .join(PostTag, PostTag.post_id == Post.id)
        .where(
            PostTag.tagged_user_id == user_id,
            PostTag.deleted_at.is_(None),
            Post.deleted_at.is_(None),
        )
        .options(selectinload(Post.media))
        .order_by(Post.created_at.desc())
    )
    posts = list(result.scalars().all())
    return await _enrich_to_feed_responses(posts, requesting_user_id, db)


async def record_post_view(
    post_id: uuid.UUID,
    viewer_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Record one play of a video post and atomically increment views_count."""
    from sqlalchemy import update as sa_update

    db.add(PostView(post_id=post_id, viewer_id=viewer_id))
    await db.execute(
        sa_update(Post)
        .where(Post.id == post_id, Post.deleted_at.is_(None))
        .values(views_count=Post.views_count + 1)
    )
    await db.commit()


async def record_post_view_bg(post_id: uuid.UUID, viewer_id: uuid.UUID) -> None:
    """Background-safe wrapper — creates its own DB session so the view
    recording can run after the HTTP response is already sent."""
    from app.core.database.session import async_session

    async with async_session() as db:
        await record_post_view(post_id=post_id, viewer_id=viewer_id, db=db)


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

    tagged_users: list[TaggedUserResponse] = []
    for tagged_user_id in req.tagged_user_ids:
        if tagged_user_id == user_id:
            continue
        db.add(PostTag(post_id=post.id, tagged_user_id=tagged_user_id))

    await db.commit()

    # A new video post invalidates the cached reel feed
    if req.media_type == MediaType.video:
        from app.core.cache.redis_cache import cache

        await cache.delete_pattern("reels:base:*")

    stmt = select(Post).where(Post.id == post.id).options(selectinload(Post.media))
    result = await db.execute(stmt)
    post = result.scalar_one()

    if req.tagged_user_ids:
        user_rows = await db.execute(
            select(User.id, User.username, User.display_name, User.avatar_url).where(
                User.id.in_(req.tagged_user_ids)
            )
        )
        tagged_users = [
            TaggedUserResponse(
                id=row.id,
                username=row.username,
                display_name=row.display_name,
                avatar_url=row.avatar_url,
            )
            for row in user_rows
        ]

    return _build_post_response(post, tagged_users=tagged_users)
