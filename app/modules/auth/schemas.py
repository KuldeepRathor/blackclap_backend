import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegister(BaseModel):
    """Schema for validating user registration requests."""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=6, max_length=100)


class UserResponse(BaseModel):
    """Schema for serializing User profiles in responses."""

    id: uuid.UUID
    email: EmailStr
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """Schema for standard OAuth2 token responses."""

    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Schema for parsed JWT token payload data."""

    user_id: Optional[str] = None
