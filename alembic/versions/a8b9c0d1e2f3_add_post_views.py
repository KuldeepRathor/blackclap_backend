"""add_post_views

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-06-27 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, Sequence[str], None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "posts",
        sa.Column("views_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "post_views",
        sa.Column("post_id", sa.UUID(), nullable=False),
        sa.Column("viewer_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["viewer_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_post_views_post_id"), "post_views", ["post_id"], unique=False)
    op.create_index(op.f("ix_post_views_viewer_id"), "post_views", ["viewer_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_post_views_viewer_id"), table_name="post_views")
    op.drop_index(op.f("ix_post_views_post_id"), table_name="post_views")
    op.drop_table("post_views")
    op.drop_column("posts", "views_count")
