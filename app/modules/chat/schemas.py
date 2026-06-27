import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MessageType(str, Enum):
    text = "text"
    image = "image"
    video = "video"
    system = "system"


class ConversationType(str, Enum):
    direct = "direct"
    group = "group"


# ---------------------------------------------------------------------------
# Shared snippets
# ---------------------------------------------------------------------------

class UserSnippet(BaseModel):
    """Minimal author/participant projection embedded in chat responses."""

    id: uuid.UUID
    username: str
    display_name: str | None = None
    avatar_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ParticipantInfo(BaseModel):
    user: UserSnippet
    role: str = "member"
    last_read_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID
    sender: UserSnippet | None = None
    type: str = MessageType.text.value
    content: str | None = None
    media_url: str | None = None
    media_type: str | None = None
    thumbnail_url: str | None = None
    client_message_id: uuid.UUID | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageListResponse(BaseModel):
    messages: list[MessageResponse]
    next_cursor: str | None = None


class SendMessageRequest(BaseModel):
    content: str | None = Field(None, max_length=4000)
    # Client-generated UUID for idempotent sends + optimistic reconciliation.
    client_message_id: uuid.UUID | None = None
    type: MessageType = MessageType.text
    media_url: str | None = Field(None, max_length=1024)
    media_type: str | None = Field(None, max_length=20)
    thumbnail_url: str | None = Field(None, max_length=1024)

    @model_validator(mode="after")
    def validate_message(self) -> "SendMessageRequest":
        if self.type == MessageType.text:
            if not self.content or not self.content.strip():
                raise ValueError("Text messages require non-empty content")
        elif self.type in (MessageType.image, MessageType.video):
            if not self.media_url:
                raise ValueError("Media messages require a media_url")
        return self


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

class ConversationResponse(BaseModel):
    id: uuid.UUID
    type: str = ConversationType.direct.value
    title: str | None = None
    avatar_url: str | None = None
    participants: list[ParticipantInfo] = Field(default_factory=list)
    last_message: MessageResponse | None = None
    last_message_preview: str | None = None
    last_message_at: datetime | None = None
    last_message_sender_id: uuid.UUID | None = None
    unread_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationListResponse(BaseModel):
    conversations: list[ConversationResponse]
    next_cursor: str | None = None


class CreateConversationRequest(BaseModel):
    """Get-or-create a 1:1 DM with another user."""

    participant_id: uuid.UUID


# ---------------------------------------------------------------------------
# Read state
# ---------------------------------------------------------------------------

class MarkReadRequest(BaseModel):
    last_read_message_id: uuid.UUID


class MarkReadResponse(BaseModel):
    unread_count: int = 0
    last_read_at: datetime | None = None


class UnreadCountResponse(BaseModel):
    total_unread: int = 0
