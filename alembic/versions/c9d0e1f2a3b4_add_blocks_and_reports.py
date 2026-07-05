"""add_blocks_and_reports

Revision ID: c9d0e1f2a3b4
Revises: a8b9c0d1e2f3
Create Date: 2026-07-05 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "a8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "blocks",
        sa.Column("blocker_id", sa.UUID(), nullable=False),
        sa.Column("blocked_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["blocker_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["blocked_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("blocker_id", "blocked_id", name="uq_block_pair"),
    )
    op.create_index(op.f("ix_blocks_blocker_id"), "blocks", ["blocker_id"], unique=False)
    op.create_index(op.f("ix_blocks_blocked_id"), "blocks", ["blocked_id"], unique=False)

    op.create_table(
        "reports",
        sa.Column("reporter_id", sa.UUID(), nullable=False),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("target_id", sa.UUID(), nullable=False),
        sa.Column("reason", sa.String(length=30), nullable=False),
        sa.Column("details", sa.String(length=1000), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reports_reporter_id"), "reports", ["reporter_id"], unique=False)
    op.create_index(op.f("ix_reports_target_type"), "reports", ["target_type"], unique=False)
    op.create_index(op.f("ix_reports_target_id"), "reports", ["target_id"], unique=False)
    op.create_index(op.f("ix_reports_status"), "reports", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_reports_status"), table_name="reports")
    op.drop_index(op.f("ix_reports_target_id"), table_name="reports")
    op.drop_index(op.f("ix_reports_target_type"), table_name="reports")
    op.drop_index(op.f("ix_reports_reporter_id"), table_name="reports")
    op.drop_table("reports")

    op.drop_index(op.f("ix_blocks_blocked_id"), table_name="blocks")
    op.drop_index(op.f("ix_blocks_blocker_id"), table_name="blocks")
    op.drop_table("blocks")
