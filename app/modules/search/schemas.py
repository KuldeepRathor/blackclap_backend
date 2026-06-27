import uuid

from pydantic import BaseModel, ConfigDict

from app.modules.posts.schemas import FeedPostResponse


class SearchUserResult(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str | None
    avatar_url: str | None
    bio: str | None
    is_following: bool = False

    model_config = ConfigDict(from_attributes=True)


# Reuse FeedPostResponse for post search results — identical shape, no duplication.
SearchPostResult = FeedPostResponse


class SearchResponse(BaseModel):
    users: list[SearchUserResult] = []
    posts: list[SearchPostResult] = []
    next_cursor: str | None = None
