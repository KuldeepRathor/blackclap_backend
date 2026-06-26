from pydantic import BaseModel, ConfigDict


class FollowResponse(BaseModel):
    is_following: bool
    followers_count: int
    following_count: int

    model_config = ConfigDict(from_attributes=True)
