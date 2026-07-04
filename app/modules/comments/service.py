import base64
import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.comments.models import Comment
from app.modules.comments.schemas import (
    CommentResponse,
    CommentsListResponse,
    CommentUserSnippet,
    CreateCommentRequest,
    RepliesListResponse,
)
from app.modules.posts.models import Post

# ---------------------------------------------------------------------------
# Cursor helpers
# Cursor encodes (created_at ISO string, id) so pagination is stable and cheap.
# Top-level comments: newest first (DESC). Replies: oldest first (ASC).
# ---------------------------------------------------------------------------


def _encode_cursor(created_at: datetime, row_id: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{row_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        dt_str, id_str = raw.split("|", 1)
        return datetime.fromisoformat(dt_str), uuid.UUID(id_str)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cursor"
        )


def _to_response(c: Comment, replies_count: int = 0) -> CommentResponse:
    return CommentResponse(
        id=c.id,
        post_id=c.post_id,
        user_id=c.user_id,
        user=CommentUserSnippet.model_validate(c.user),
        content=c.content,
        parent_id=c.parent_id,
        replies_count=replies_count,
        created_at=c.created_at,
    )


# ---------------------------------------------------------------------------
# Get top-level comments (newest first, cursor-paginated)
# ---------------------------------------------------------------------------


async def get_comments(
    post_id: uuid.UUID,
    db: AsyncSession,
    limit: int = 20,
    after_cursor: str | None = None,
) -> CommentsListResponse:
    post = await db.get(Post, post_id)
    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    stmt = (
        select(Comment)
        .where(Comment.post_id == post_id, Comment.parent_id.is_(None))
        .options(selectinload(Comment.user))
        .order_by(Comment.created_at.desc(), Comment.id.desc())
    )

    if after_cursor:
        cursor_dt, cursor_id = _decode_cursor(after_cursor)
        stmt = stmt.where(
            or_(
                Comment.created_at < cursor_dt,
                (Comment.created_at == cursor_dt) & (Comment.id < cursor_id),
            )
        )

    # Fetch one extra to know if there's a next page
    stmt = stmt.limit(limit + 1)
    result = await db.execute(stmt)
    rows = list(result.scalars().all())

    has_more = len(rows) > limit
    comments = rows[:limit]

    # Batch-fetch reply counts for this page
    comment_ids = [c.id for c in comments]
    reply_counts: dict[uuid.UUID, int] = {}
    if comment_ids:
        rc_rows = await db.execute(
            select(Comment.parent_id, func.count().label("cnt"))
            .where(Comment.parent_id.in_(comment_ids))
            .group_by(Comment.parent_id)
        )
        reply_counts = {row.parent_id: row.cnt for row in rc_rows}

    responses = [_to_response(c, reply_counts.get(c.id, 0)) for c in comments]

    next_cursor = (
        _encode_cursor(comments[-1].created_at, comments[-1].id)
        if has_more and comments
        else None
    )

    return CommentsListResponse(comments=responses, next_cursor=next_cursor)


# ---------------------------------------------------------------------------
# Get replies for a comment (oldest first, cursor-paginated)
# ---------------------------------------------------------------------------


async def get_replies(
    post_id: uuid.UUID,
    comment_id: uuid.UUID,
    db: AsyncSession,
    limit: int = 10,
    after_cursor: str | None = None,
) -> RepliesListResponse:
    parent = await db.get(Comment, comment_id)
    if parent is None or parent.post_id != post_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found"
        )

    stmt = (
        select(Comment)
        .where(Comment.parent_id == comment_id)
        .options(selectinload(Comment.user))
        .order_by(Comment.created_at.asc(), Comment.id.asc())
    )

    if after_cursor:
        cursor_dt, cursor_id = _decode_cursor(after_cursor)
        stmt = stmt.where(
            or_(
                Comment.created_at > cursor_dt,
                (Comment.created_at == cursor_dt) & (Comment.id > cursor_id),
            )
        )

    stmt = stmt.limit(limit + 1)
    result = await db.execute(stmt)
    rows = list(result.scalars().all())

    has_more = len(rows) > limit
    replies = rows[:limit]

    next_cursor = (
        _encode_cursor(replies[-1].created_at, replies[-1].id)
        if has_more and replies
        else None
    )

    return RepliesListResponse(
        replies=[_to_response(r) for r in replies], next_cursor=next_cursor
    )


# ---------------------------------------------------------------------------
# Create comment / reply
# ---------------------------------------------------------------------------


async def add_comment(
    post_id: uuid.UUID,
    user_id: uuid.UUID,
    req: CreateCommentRequest,
    db: AsyncSession,
) -> CommentResponse:
    post = await db.get(Post, post_id)
    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    if req.parent_id is not None:
        parent = await db.get(Comment, req.parent_id)
        if parent is None or parent.post_id != post_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Parent comment not found"
            )
        # Only one level of threading (replies to top-level comments only)
        if parent.parent_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reply to a reply",
            )

    comment = Comment(
        post_id=post_id, user_id=user_id, content=req.content, parent_id=req.parent_id
    )
    db.add(comment)
    await db.commit()

    result = await db.execute(
        select(Comment)
        .where(Comment.id == comment.id)
        .options(selectinload(Comment.user))
    )
    comment = result.scalar_one()
    return _to_response(comment)


# ---------------------------------------------------------------------------
# Delete comment
# ---------------------------------------------------------------------------


async def delete_comment(
    comment_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    comment = await db.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found"
        )
    if comment.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete another user's comment",
        )
    await db.delete(comment)
    await db.commit()
