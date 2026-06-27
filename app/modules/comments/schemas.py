import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreateCommentRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)
    parent_id: uuid.UUID | None = None


class CommentUserSnippet(BaseModel):
    id: uuid.UUID
    username: str
    avatar_url: str | None

    model_config = ConfigDict(from_attributes=True)


class CommentResponse(BaseModel):
    id: uuid.UUID
    post_id: uuid.UUID
    user_id: uuid.UUID
    user: CommentUserSnippet
    content: str
    parent_id: uuid.UUID | None
    replies_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommentsListResponse(BaseModel):
    comments: list[CommentResponse]
    next_cursor: str | None  # opaque cursor; None means no more pages


class RepliesListResponse(BaseModel):
    replies: list[CommentResponse]
    next_cursor: str | None
