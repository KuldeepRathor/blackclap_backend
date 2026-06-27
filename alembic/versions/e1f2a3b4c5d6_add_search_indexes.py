"""add search indexes

Revision ID: e1f2a3b4c5d6
Revises: 1e01684aaea7
Create Date: 2026-06-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "1e01684aaea7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pg_trgm extension for trigram-based user search (ILIKE acceleration)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # GIN trigram indexes on users for fast ILIKE '%query%' at lakhs scale
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_username_trgm "
        "ON users USING GIN (username gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_display_name_trgm "
        "ON users USING GIN (display_name gin_trgm_ops)"
    )

    # GIN expression index for full-text search on post captions at millions scale.
    # coalesce(caption, '') ensures NULL captions are indexed as empty tsvector
    # (they match no queries but don't break the index).
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_posts_caption_fts "
        "ON posts USING GIN (to_tsvector('english', coalesce(caption, '')))"
    )

    # Composite B-tree for cursor-paginated post search queries.
    # All post search queries filter deleted_at IS NULL and order by created_at DESC.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_posts_deleted_created "
        "ON posts (deleted_at, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_posts_deleted_created")
    op.execute("DROP INDEX IF EXISTS idx_posts_caption_fts")
    op.execute("DROP INDEX IF EXISTS idx_users_display_name_trgm")
    op.execute("DROP INDEX IF EXISTS idx_users_username_trgm")
    # Note: we do NOT drop the pg_trgm extension in downgrade because other
    # parts of the database might depend on it.
