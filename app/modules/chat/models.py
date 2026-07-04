import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models.base import BaseModel

if TYPE_CHECKING:
    from app.modules.users.models import User


class Conversation(BaseModel):
    """
    A conversation thread. Unified model for 1:1 DMs and group chats:
      - type == "direct": exactly 2 participants, dedup-keyed via `dm_key`.
      - type == "group":  N participants, `dm_key` is NULL (group fields used).

    Group-only columns (title/avatar_url/created_by) and the denormalized
    last-message fields are populated as the product grows; everything except
    `type` is nullable so later phases need only additive migrations.
    """

    __tablename__ = "conversations"

    # "direct" | "group"  (Phase 1 only creates "direct")
    type: Mapped[str] = mapped_column(String(10), nullable=False, default="direct")

    # Group-only fields (NULL for direct conversations). Designed now, used later.
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Deterministic dedup key for 1:1 DMs: f"{min(a,b)}:{max(a,b)}" of the two
    # user UUIDs. NULL for groups. A partial unique index enforces "one DM per pair".
    dm_key: Mapped[str | None] = mapped_column(String(73), nullable=True)

    # --- Denormalized "last message" so the conversation-list screen never
    #     has to scan the messages table. Updated transactionally on send. ---
    # Intentionally NOT a ForeignKey: a hard FK both ways (messages -> conversation
    # and conversation -> last message) creates a circular dependency.
    last_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    last_message_preview: Mapped[str | None] = mapped_column(String(200), nullable=True)
    last_message_sender_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    participants: Mapped[list["ConversationParticipant"]] = relationship(
        "ConversationParticipant",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        # 1:1 dedup enforced at the DB level — only applies to direct rows.
        Index(
            "uq_conversation_dm_key",
            "dm_key",
            unique=True,
            postgresql_where=text("dm_key IS NOT NULL"),
        ),
    )

    def __repr__(self) -> str:
        return f"<Conversation id={self.id} type={self.type}>"


class ConversationParticipant(BaseModel):
    """
    Membership of a user in a conversation + that user's per-conversation read
    state. A DM has exactly 2 rows; a group has N rows.

    `last_read_message_id` + `unread_count` cover DM read receipts and unread
    badges without a per-message-per-user table.
    """

    __tablename__ = "conversation_participants"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # "member" | "admin"  (group roles used in Phase 3; DMs are always "member")
    role: Mapped[str] = mapped_column(String(10), nullable=False, default="member")

    # --- Per-user read state ---
    last_read_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    last_read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    unread_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    # --- Group membership lifecycle (used in Phase 3; harmless to add now) ---
    joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    left_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_muted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="participants"
    )
    user: Mapped["User"] = relationship("User", lazy="joined")

    __table_args__ = (
        UniqueConstraint("conversation_id", "user_id", name="uq_participant_pair"),
        # "all conversations for user X" -> join participants(user_id) -> conversations.
        Index("ix_participant_user_conv", "user_id", "conversation_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<ConversationParticipant conv={self.conversation_id} "
            f"user={self.user_id} unread={self.unread_count}>"
        )


class Message(BaseModel):
    """
    A single message in a conversation. Phase 1 sends only `type == "text"`;
    media columns and `type` variants ("image"/"video"/"system") are present
    now so Phase 2/3 require no schema changes to the core send path.
    """

    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # "text" | "image" | "video" | "system"
    type: Mapped[str] = mapped_column(String(12), nullable=False, default="text")

    # Text body. NULL allowed for pure-media messages (Phase 2).
    content: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Media (Phase 2). Reuses the Azure blob_url produced by /uploads. ---
    media_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    media_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Client-generated idempotency key: dedups retries and lets the client match
    # its optimistic local message to the server-persisted one.
    client_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    sender: Mapped["User"] = relationship("User", lazy="joined")

    __table_args__ = (
        # THE message-history index: page a conversation's messages newest-first.
        Index("ix_messages_conv_created", "conversation_id", "created_at", "id"),
        # Idempotent send: a given (conversation, client_message_id) inserts once.
        Index(
            "uq_messages_client_id",
            "conversation_id",
            "client_message_id",
            unique=True,
            postgresql_where=text("client_message_id IS NOT NULL"),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Message id={self.id} conv={self.conversation_id} "
            f"sender={self.sender_id}>"
        )
