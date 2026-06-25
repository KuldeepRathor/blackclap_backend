import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.comments.models import Comment
from app.modules.comments.schemas import (
    CommentResponse,
    CommentsListResponse,
    CreateCommentRequest,
)
from app.modules.posts.models import Post


async def get_comments(
    post_id: uuid.UUID,
    db: AsyncSession,
    limit: int = 20,
    offset: int = 0,
) -> CommentsListResponse:
    post = await db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    # Top-level comments only (no replies)
    stmt = (
        select(Comment)
        .where(Comment.post_id == post_id, Comment.parent_id.is_(None))
        .options(selectinload(Comment.user))
        .order_by(Comment.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    comments = result.scalars().all()

    total = await db.scalar(
        select(func.count()).where(Comment.post_id == post_id, Comment.parent_id.is_(None))
    ) or 0

    # Batch fetch reply counts
    comment_ids = [c.id for c in comments]
    reply_counts: dict[uuid.UUID, int] = {}
    if comment_ids:
        rows = await db.execute(
            select(Comment.parent_id, func.count().label("cnt"))
            .where(Comment.parent_id.in_(comment_ids))
            .group_by(Comment.parent_id)
        )
        reply_counts = {row.parent_id: row.cnt for row in rows}

    responses = [
        CommentResponse(
            id=c.id,
            post_id=c.post_id,
            user_id=c.user_id,
            user=c.user,
            content=c.content,
            parent_id=c.parent_id,
            replies_count=reply_counts.get(c.id, 0),
            created_at=c.created_at,
        )
        for c in comments
    ]

    return CommentsListResponse(
        comments=responses,
        total=total,
        has_more=offset + limit < total,
    )


async def add_comment(
    post_id: uuid.UUID,
    user_id: uuid.UUID,
    req: CreateCommentRequest,
    db: AsyncSession,
) -> CommentResponse:
    post = await db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    if req.parent_id is not None:
        parent = await db.get(Comment, req.parent_id)
        if parent is None or parent.post_id != post_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent comment not found")

    comment = Comment(post_id=post_id, user_id=user_id, content=req.content, parent_id=req.parent_id)
    db.add(comment)
    await db.commit()

    result = await db.execute(
        select(Comment).where(Comment.id == comment.id).options(selectinload(Comment.user))
    )
    comment = result.scalar_one()

    return CommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        user_id=comment.user_id,
        user=comment.user,
        content=comment.content,
        parent_id=comment.parent_id,
        replies_count=0,
        created_at=comment.created_at,
    )


async def delete_comment(
    comment_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    comment = await db.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    if comment.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete another user's comment")
    await db.delete(comment)
    await db.commit()
