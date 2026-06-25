import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.security.auth import get_current_user
from app.modules.comments.schemas import (
    CommentResponse,
    CommentsListResponse,
    CreateCommentRequest,
)
from app.modules.comments.service import add_comment, delete_comment, get_comments
from app.modules.users.models import User

router = APIRouter(prefix="/posts", tags=["Comments"])


@router.get("/{post_id}/comments", response_model=CommentsListResponse)
async def list_comments_endpoint(
    post_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommentsListResponse:
    return await get_comments(post_id=post_id, db=db, limit=limit, offset=offset)


@router.post(
    "/{post_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_comment_endpoint(
    post_id: uuid.UUID,
    req: CreateCommentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommentResponse:
    return await add_comment(post_id=post_id, user_id=current_user.id, req=req, db=db)


@router.delete("/{post_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment_endpoint(
    post_id: uuid.UUID,
    comment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await delete_comment(comment_id=comment_id, user_id=current_user.id, db=db)
