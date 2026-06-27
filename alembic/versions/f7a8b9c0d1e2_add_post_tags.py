"""add_post_tags

Revision ID: f7a8b9c0d1e2
Revises: e1f2a3b4c5d6
Create Date: 2026-06-27 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = ("b7c8d9e0f1a2", "e1f2a3b4c5d6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "post_tags",
        sa.Column("post_id", sa.UUID(), nullable=False),
        sa.Column("tagged_user_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tagged_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("post_id", "tagged_user_id", name="uq_post_tags_post_user"),
    )
    op.create_index(op.f("ix_post_tags_post_id"), "post_tags", ["post_id"], unique=False)
    op.create_index(op.f("ix_post_tags_tagged_user_id"), "post_tags", ["tagged_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_post_tags_tagged_user_id"), table_name="post_tags")
    op.drop_index(op.f("ix_post_tags_post_id"), table_name="post_tags")
    op.drop_table("post_tags")
