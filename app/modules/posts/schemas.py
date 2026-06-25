import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MediaType(str, Enum):
    image = "image"
    video = "video"
    text = "text"


class PostMediaResponse(BaseModel):
    id: uuid.UUID
    media_url: str
    media_type: str
    thumbnail_url: str | None
    order: int

    model_config = ConfigDict(from_attributes=True)


class CreatePostRequest(BaseModel):
    caption: str | None = Field(None, max_length=2200)
    location: str | None = Field(None, max_length=255)
    media_type: MediaType = MediaType.text
    media_urls: list[str] = Field(default_factory=list, max_length=5)
    thumbnail_url: str | None = Field(None, description="Thumbnail blob URL for video posts")

    @model_validator(mode="after")
    def validate_post(self) -> "CreatePostRequest":
        if not self.caption and not self.media_urls:
            raise ValueError("Post must have a caption or at least one media item")
        if self.media_type == MediaType.image and len(self.media_urls) > 5:
            raise ValueError("Maximum 5 images allowed per post")
        if self.media_type == MediaType.video and len(self.media_urls) > 1:
            raise ValueError("Only 1 video allowed per post")
        if self.media_type != MediaType.text and not self.media_urls:
            raise ValueError("media_urls required when media_type is image or video")
        if self.thumbnail_url and self.media_type != MediaType.video:
            raise ValueError("thumbnail_url is only valid for video posts")
        return self


class PostResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    caption: str | None
    location: str | None
    media_type: str
    media: list[PostMediaResponse]
    likes_count: int = 0
    comments_count: int = 0
    is_liked: bool = False
    is_saved: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
