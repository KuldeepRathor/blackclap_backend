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
    refresh_token: Optional[str] = None
    token_type: str = "bearer"


class UserLogin(BaseModel):
    """Schema for validating user login requests via JSON."""

    email_or_username: str
    password: str


class AuthResponse(BaseModel):
    """Unified response containing tokens and user profile information."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenData(BaseModel):
    """Schema for parsed JWT token payload data."""

    user_id: Optional[str] = None


class MessageResponse(BaseModel):
    """Generic message response (used for password-reset endpoints)."""

    message: str


class ForgotPasswordRequest(BaseModel):
    """Request a password-reset code be sent to the given email."""

    email: EmailStr


class VerifyResetCodeRequest(BaseModel):
    """Validate a reset code without consuming it (gates the new-password screen)."""

    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class ResetPasswordRequest(BaseModel):
    """Consume a reset code and set a new password."""

    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    new_password: str = Field(..., min_length=6, max_length=100)
