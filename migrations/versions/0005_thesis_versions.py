"""Add immutable point-in-time thesis versions.

Revision ID: 0005_thesis_versions
Revises: 0004_india_context_data
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_thesis_versions"
down_revision: str | None = "0004_india_context_data"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "thesis_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("symbol", sa.String(32), sa.ForeignKey("assets.symbol"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("previous_version_id", sa.String(36)),
        sa.Column("snapshot_hash", sa.String(64), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Numeric(8, 6), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("symbol", "snapshot_hash", name="uq_thesis_symbol_snapshot"),
    )
    op.create_index("ix_thesis_symbol_cutoff", "thesis_versions", ["symbol", "cutoff"])
    op.create_index("ix_thesis_symbol_created", "thesis_versions", ["symbol", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_thesis_symbol_created", table_name="thesis_versions")
    op.drop_index("ix_thesis_symbol_cutoff", table_name="thesis_versions")
    op.drop_table("thesis_versions")
