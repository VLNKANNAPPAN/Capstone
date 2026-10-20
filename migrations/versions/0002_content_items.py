"""Add normalized news and social content.

Revision ID: 0002_content_items
Revises: 0001_data_foundation
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_content_items"
down_revision: str | None = "0001_data_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "content_items",
        sa.Column("source", sa.String(64), primary_key=True),
        sa.Column("external_id", sa.String(255), primary_key=True),
        sa.Column("content_type", sa.String(16), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("author", sa.String(255)),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("symbols", sa.JSON(), nullable=False),
        sa.Column("language", sa.String(32)),
        sa.Column("sentiment_score", sa.Numeric(8, 6)),
        sa.Column("engagement_score", sa.Numeric(24, 6)),
        sa.Column("metadata", sa.JSON(), nullable=False),
    )
    op.create_index("ix_content_type_published", "content_items", ["content_type", "published_at"])
    op.create_index("ix_content_available", "content_items", ["available_at"])


def downgrade() -> None:
    op.drop_index("ix_content_available", table_name="content_items")
    op.drop_index("ix_content_type_published", table_name="content_items")
    op.drop_table("content_items")
