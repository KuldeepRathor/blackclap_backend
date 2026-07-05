import base64
import json
import re
import uuid
from datetime import datetime

from sqlalchemy import ColumnElement, and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.follows.models import Follow
from app.modules.moderation.service import get_blocked_user_ids
from app.modules.posts.models import Post
from app.modules.posts.service import _enrich_to_feed_responses
from app.modules.search.schemas import (
    SearchPostResult,
    SearchResponse,
    SearchUserResult,
)
from app.modules.users.models import User

_MIN_QUERY_LENGTH = 2
_PUNCTUATION_RE = re.compile(r"[^\w\s]")
_ILIKE_ESCAPE_RE = re.compile(r"([%_\\])")


def _escape_ilike(s: str) -> str:
    """Escape ILIKE special characters so user input is treated as literal text."""
    return _ILIKE_ESCAPE_RE.sub(r"\\\1", s)


def _sanitise_query(query: str) -> str | None:
    """Strip punctuation/whitespace; return None if the result is too short for FTS."""
    sanitised = _PUNCTUATION_RE.sub("", query).strip()
    return sanitised if len(sanitised) >= _MIN_QUERY_LENGTH else None


def _encode_cursor(created_at: datetime, post_id: uuid.UUID) -> str:
    payload = {"ts": created_at.isoformat(), "id": str(post_id)}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID] | None:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        return datetime.fromisoformat(payload["ts"]), uuid.UUID(payload["id"])
    except Exception:
        # Malformed cursor → treat as first page (safe degradation).
        return None


async def search_users(
    query: str,
    requesting_user_id: uuid.UUID,
    db: AsyncSession,
    limit: int = 20,
    offset: int = 0,
) -> list[SearchUserResult]:
    escaped = _escape_ilike(query.strip())
    ilike_pattern = f"%{escaped}%"
    prefix_pattern = f"{escaped}%"

    blocked_ids = await get_blocked_user_ids(requesting_user_id, db)

    stmt = select(User).where(
        User.deleted_at.is_(None),
        User.is_active.is_(True),
        or_(
            User.username.ilike(ilike_pattern, escape="\\"),
            User.display_name.ilike(ilike_pattern, escape="\\"),
        ),
    )
    if blocked_ids:
        stmt = stmt.where(User.id.notin_(blocked_ids))
    stmt = (
        stmt.order_by(
            # Prefix matches on username rank highest, then display_name prefix,
            # then mid-string matches — provides intuitive relevance ordering.
            text(
                "CASE "
                "WHEN username ILIKE :prefix THEN 0 "
                "WHEN display_name ILIKE :prefix THEN 1 "
                "ELSE 2 END"
            ).bindparams(prefix=prefix_pattern),
            User.username,
        )
        .limit(limit)
        .offset(offset)
    )

    result = await db.execute(stmt)
    users = list(result.scalars().all())

    if not users:
        return []

    user_ids = [u.id for u in users]

    following_rows = await db.execute(
        select(Follow.followed_id).where(
            Follow.follower_id == requesting_user_id,
            Follow.followed_id.in_(user_ids),
        )
    )
    following_set: set[uuid.UUID] = {row.followed_id for row in following_rows}

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


async def search_posts(
    query: str,
    requesting_user_id: uuid.UUID,
    db: AsyncSession,
    limit: int = 20,
    cursor: str | None = None,
) -> tuple[list[SearchPostResult], str | None]:
    sanitised = _sanitise_query(query)
    if not sanitised:
        return [], None

    fts_vector = func.to_tsvector("english", func.coalesce(Post.caption, ""))
    fts_query = func.plainto_tsquery("english", sanitised)

    conditions: list[ColumnElement[bool]] = [
        Post.deleted_at.is_(None),
        fts_vector.op("@@")(fts_query),
    ]

    blocked_ids = await get_blocked_user_ids(requesting_user_id, db)
    if blocked_ids:
        conditions.append(Post.user_id.notin_(blocked_ids))

    if cursor:
        parsed = _decode_cursor(cursor)
        if parsed:
            cursor_ts, cursor_id = parsed
            # Keyset pagination: rows older than the cursor position.
            # The compound OR handles ties in created_at correctly.
            conditions.append(
                or_(
                    Post.created_at < cursor_ts,
                    and_(Post.created_at == cursor_ts, Post.id < cursor_id),
                )
            )

    stmt = (
        select(Post)
        .where(*conditions)
        .options(selectinload(Post.media))
        .order_by(Post.created_at.desc(), Post.id.desc())
        .limit(limit + 1)  # fetch one extra to determine whether a next page exists
    )

    result = await db.execute(stmt)
    posts = list(result.scalars().all())

    has_more = len(posts) > limit
    if has_more:
        posts = posts[:limit]

    next_cursor = (
        _encode_cursor(posts[-1].created_at, posts[-1].id) if has_more else None
    )

    enriched = await _enrich_to_feed_responses(posts, requesting_user_id, db)
    return enriched, next_cursor


async def search_all(
    query: str,
    requesting_user_id: uuid.UUID,
    db: AsyncSession,
) -> SearchResponse:
    """Combined search returning a preview of both users (5) and posts (10)."""
    users = await search_users(query, requesting_user_id, db, limit=5, offset=0)
    posts, next_cursor = await search_posts(query, requesting_user_id, db, limit=10)
    return SearchResponse(users=users, posts=posts, next_cursor=next_cursor)
