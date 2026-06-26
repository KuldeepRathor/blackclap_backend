"""add_follows_table

Revision ID: 1e01684aaea7
Revises: d4e5f6a7b8c9
Create Date: 2026-06-27 02:06:53.380142

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1e01684aaea7'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "follows",
        sa.Column("follower_id", sa.UUID(), nullable=False),
        sa.Column("followed_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["followed_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["follower_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("follower_id", "followed_id", name="uq_follow_pair"),
    )
    op.create_index(op.f("ix_follows_follower_id"), "follows", ["follower_id"], unique=False)
    op.create_index(op.f("ix_follows_followed_id"), "follows", ["followed_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_follows_followed_id")
    op.execute("DROP INDEX IF EXISTS ix_follows_follower_id")
    op.execute("DROP TABLE IF EXISTS follows")
