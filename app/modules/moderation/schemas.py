import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ReportTargetType(str, Enum):
    user = "user"
    post = "post"
    comment = "comment"


class ReportReason(str, Enum):
    spam = "spam"
    harassment = "harassment"
    hate_speech = "hate_speech"
    nudity = "nudity"
    violence = "violence"
    fake_account = "fake_account"
    self_harm = "self_harm"
    other = "other"


class BlockActionResponse(BaseModel):
    is_blocked: bool

    model_config = ConfigDict(from_attributes=True)


class BlockedUserResponse(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str | None
    avatar_url: str | None
    blocked_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportCreate(BaseModel):
    target_type: ReportTargetType
    target_id: uuid.UUID
    reason: ReportReason
    details: str | None = Field(default=None, max_length=1000)


class ReportResponse(BaseModel):
    id: uuid.UUID
    target_type: ReportTargetType
    target_id: uuid.UUID
    reason: ReportReason
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
