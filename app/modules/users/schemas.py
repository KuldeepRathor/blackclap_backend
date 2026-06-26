from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.modules.auth.schemas import UserResponse


class UserUpdate(BaseModel):
    """Schema for validating user profile update requests."""

    display_name: Optional[str] = Field(None, max_length=100)
    username: Optional[str] = Field(
        None, min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$"
    )
    bio: Optional[str] = Field(None, max_length=150)
    email: Optional[EmailStr] = None
    avatar_url: Optional[str] = Field(None, max_length=512)


class UserProfileResponse(UserResponse):
    """Schema for serializing full User Profiles including social and posting stats."""

    posts_count: int = 0
    followers_count: int = 0
    following_count: int = 0
    is_following: bool = False
