"""add_comments_composite_index

Revision ID: a2b3c4d5e6f7
Revises: e1f2a3b4c5d6
Create Date: 2026-06-27 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Covers both top-level (parent_id IS NULL) and reply (parent_id = X) cursor queries.
    # Query shape: WHERE post_id = X AND parent_id [IS NULL | = Y]
    #              AND (created_at [<|>] :dt OR (created_at = :dt AND id [<|>] :id))
    #              ORDER BY created_at [DESC|ASC], id [DESC|ASC]
    op.create_index(
        "ix_comments_post_parent_created_at_id",
        "comments",
        ["post_id", "parent_id", "created_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_comments_post_parent_created_at_id", table_name="comments")
