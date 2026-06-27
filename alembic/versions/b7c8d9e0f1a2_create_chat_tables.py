"""create_chat_tables

Revision ID: b7c8d9e0f1a2
Revises: a2b3c4d5e6f7
Create Date: 2026-06-27 19:00:00.000000

Creates the unified chat schema: conversations, conversation_participants,
messages. Designed so 1:1 DMs and group chats share the same tables; group and
media columns are present-but-nullable so later phases need only additive
migrations.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, Sequence[str], None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- conversations ---
    op.create_table(
        "conversations",
        sa.Column("type", sa.String(length=10), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=True),
        sa.Column("avatar_url", sa.String(length=1024), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("dm_key", sa.String(length=73), nullable=True),
        sa.Column("last_message_id", sa.UUID(), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_preview", sa.String(length=200), nullable=True),
        sa.Column("last_message_sender_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_conversations_last_message_at"),
        "conversations",
        ["last_message_at"],
        unique=False,
    )
    # Partial unique index — enforces "one DM per user pair" (groups have NULL dm_key).
    op.create_index(
        "uq_conversation_dm_key",
        "conversations",
        ["dm_key"],
        unique=True,
        postgresql_where=sa.text("dm_key IS NOT NULL"),
    )

    # --- conversation_participants ---
    op.create_table(
        "conversation_participants",
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("last_read_message_id", sa.UUID(), nullable=True),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unread_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_muted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id", "user_id", name="uq_participant_pair"),
    )
    op.create_index(
        op.f("ix_conversation_participants_conversation_id"),
        "conversation_participants",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_participants_user_id"),
        "conversation_participants",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_participant_user_conv",
        "conversation_participants",
        ["user_id", "conversation_id"],
        unique=False,
    )

    # --- messages ---
    op.create_table(
        "messages",
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("sender_id", sa.UUID(), nullable=False),
        sa.Column("type", sa.String(length=12), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("media_url", sa.String(length=1024), nullable=True),
        sa.Column("media_type", sa.String(length=20), nullable=True),
        sa.Column("thumbnail_url", sa.String(length=1024), nullable=True),
        sa.Column("media_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("client_message_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_messages_sender_id"), "messages", ["sender_id"], unique=False
    )
    # The hot message-history index: page a conversation newest-first.
    op.create_index(
        "ix_messages_conv_created",
        "messages",
        ["conversation_id", "created_at", "id"],
        unique=False,
    )
    # Partial unique index — idempotent sends per (conversation, client_message_id).
    op.create_index(
        "uq_messages_client_id",
        "messages",
        ["conversation_id", "client_message_id"],
        unique=True,
        postgresql_where=sa.text("client_message_id IS NOT NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS uq_messages_client_id")
    op.execute("DROP INDEX IF EXISTS ix_messages_conv_created")
    op.execute("DROP INDEX IF EXISTS ix_messages_sender_id")
    op.execute("DROP TABLE IF EXISTS messages")

    op.execute("DROP INDEX IF EXISTS ix_participant_user_conv")
    op.execute("DROP INDEX IF EXISTS ix_conversation_participants_user_id")
    op.execute("DROP INDEX IF EXISTS ix_conversation_participants_conversation_id")
    op.execute("DROP TABLE IF EXISTS conversation_participants")

    op.execute("DROP INDEX IF EXISTS uq_conversation_dm_key")
    op.execute("DROP INDEX IF EXISTS ix_conversations_last_message_at")
    op.execute("DROP TABLE IF EXISTS conversations")
