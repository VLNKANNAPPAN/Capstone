"""Add Indian corporate disclosures and RBI macro observations.

Revision ID: 0004_india_context_data
Revises: 0003_research_analyses
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_india_context_data"
down_revision: str | None = "0003_research_analyses"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "corporate_disclosures",
        sa.Column("source", sa.String(64), primary_key=True),
        sa.Column("external_id", sa.String(255), primary_key=True),
        sa.Column("symbol", sa.String(32), sa.ForeignKey("assets.symbol"), nullable=False),
        sa.Column("exchange", sa.String(16), nullable=False),
        sa.Column("disclosure_type", sa.String(32), nullable=False),
        sa.Column("category", sa.String(255), nullable=False),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("document_url", sa.Text()),
        sa.Column("period_end", sa.String(10)),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_disclosure_symbol_published",
        "corporate_disclosures",
        ["symbol", "published_at"],
    )
    op.create_index(
        "ix_disclosure_type_available",
        "corporate_disclosures",
        ["disclosure_type", "available_at"],
    )
    op.create_table(
        "macro_observations",
        sa.Column("source", sa.String(64), primary_key=True),
        sa.Column("series_id", sa.String(128), primary_key=True),
        sa.Column("event_time", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("value", sa.Numeric(30, 10), nullable=False),
        sa.Column("unit", sa.String(64), nullable=False),
        sa.Column("frequency", sa.String(64), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_macro_series_event",
        "macro_observations",
        ["series_id", "event_time"],
    )
    op.create_index("ix_macro_available", "macro_observations", ["available_at"])


def downgrade() -> None:
    op.drop_index("ix_macro_available", table_name="macro_observations")
    op.drop_index("ix_macro_series_event", table_name="macro_observations")
    op.drop_table("macro_observations")
    op.drop_index("ix_disclosure_type_available", table_name="corporate_disclosures")
    op.drop_index("ix_disclosure_symbol_published", table_name="corporate_disclosures")
    op.drop_table("corporate_disclosures")
