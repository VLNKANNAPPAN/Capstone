"""Add Indian filing documents and normalized facts.

Revision ID: 0006_filing_intelligence
Revises: 0005_thesis_versions
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_filing_intelligence"
down_revision: str | None = "0005_thesis_versions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "filing_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("filing_external_id", sa.String(255), nullable=False),
        sa.Column("symbol", sa.String(32), sa.ForeignKey("assets.symbol"), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(64), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("content_size", sa.Integer(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("parser_version", sa.String(32), nullable=False),
        sa.Column("taxonomy", sa.String(255), nullable=False),
        sa.Column("basis", sa.String(16), nullable=False),
        sa.Column("audited", sa.Boolean()),
        sa.Column("reporting_quarter", sa.String(64)),
        sa.Column("period_start", sa.String(10)),
        sa.Column("period_end", sa.String(10)),
        sa.Column("parse_status", sa.String(16), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "source", "filing_external_id", "checksum", name="uq_filing_document_revision"
        ),
    )
    op.create_index(
        "ix_filing_document_symbol_available",
        "filing_documents",
        ["symbol", "available_at"],
    )
    op.create_table(
        "filing_facts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "document_id", sa.String(36), sa.ForeignKey("filing_documents.id"), nullable=False
        ),
        sa.Column("symbol", sa.String(32), sa.ForeignKey("assets.symbol"), nullable=False),
        sa.Column("normalized_metric", sa.String(96), nullable=False),
        sa.Column("source_concept", sa.String(255), nullable=False),
        sa.Column("context_id", sa.String(128), nullable=False),
        sa.Column("period_start", sa.String(10)),
        sa.Column("period_end", sa.String(10)),
        sa.Column("instant", sa.String(10)),
        sa.Column("value_numeric", sa.Numeric(36, 8)),
        sa.Column("value_text", sa.Text()),
        sa.Column("unit", sa.String(64)),
        sa.Column("decimals", sa.String(32)),
        sa.Column("derived", sa.Boolean(), nullable=False),
        sa.Column("formula", sa.Text()),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "document_id", "normalized_metric", "context_id", name="uq_filing_fact_metric_context"
        ),
    )
    op.create_index("ix_filing_fact_symbol_period", "filing_facts", ["symbol", "period_end"])
    op.create_index(
        "ix_filing_fact_metric_available",
        "filing_facts",
        ["normalized_metric", "available_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_filing_fact_metric_available", table_name="filing_facts")
    op.drop_index("ix_filing_fact_symbol_period", table_name="filing_facts")
    op.drop_table("filing_facts")
    op.drop_index("ix_filing_document_symbol_available", table_name="filing_documents")
    op.drop_table("filing_documents")
