"""Add auditable LLM research analyses.

Revision ID: 0003_research_analyses
Revises: 0002_content_items
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_research_analyses"
down_revision: str | None = "0002_content_items"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_analyses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("symbol", sa.String(32), sa.ForeignKey("assets.symbol"), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("prompt_version", sa.String(32), nullable=False),
        sa.Column("snapshot_hash", sa.String(64), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_research_analysis_symbol_created",
        "research_analyses",
        ["symbol", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_research_analysis_symbol_created", table_name="research_analyses")
    op.drop_table("research_analyses")
