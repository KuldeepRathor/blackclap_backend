import uuid

from pydantic import BaseModel


class LikeResponse(BaseModel):
    post_id: uuid.UUID
    likes_count: int
    is_liked: bool
