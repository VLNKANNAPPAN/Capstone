"""Create the point-in-time data foundation.

Revision ID: 0001_data_foundation
Revises: None
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_data_foundation"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("symbol", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(255)),
        sa.Column("asset_type", sa.String(32), nullable=False),
        sa.Column("exchange", sa.String(64)),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("cik", sa.String(10), unique=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "acquisition_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("dataset", sa.String(64), nullable=False),
        sa.Column("partition_key", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("raw_count", sa.Integer(), nullable=False),
        sa.Column("accepted_count", sa.Integer(), nullable=False),
        sa.Column("rejected_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text()),
    )
    op.create_index(
        "ix_acquisition_source_dataset_started",
        "acquisition_runs",
        ["source", "dataset", "started_at"],
    )
    op.create_table(
        "raw_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("dataset", sa.String(64), nullable=False),
        sa.Column("natural_key", sa.String(255), nullable=False),
        sa.Column("partition_key", sa.String(64), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True)),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "source", "dataset", "natural_key", "checksum", name="uq_raw_record_revision"
        ),
    )
    op.create_index(
        "ix_raw_partition_available",
        "raw_records",
        ["source", "dataset", "partition_key", "available_at"],
    )
    op.create_table(
        "price_bars",
        sa.Column("symbol", sa.String(32), sa.ForeignKey("assets.symbol"), primary_key=True),
        sa.Column("timeframe", sa.String(16), primary_key=True),
        sa.Column("event_time", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("source", sa.String(64), primary_key=True),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(24, 10), nullable=False),
        sa.Column("high", sa.Numeric(24, 10), nullable=False),
        sa.Column("low", sa.Numeric(24, 10), nullable=False),
        sa.Column("close", sa.Numeric(24, 10), nullable=False),
        sa.Column("volume", sa.Numeric(28, 8), nullable=False),
        sa.Column("vwap", sa.Numeric(24, 10)),
        sa.Column("trade_count", sa.Integer()),
    )
    op.create_index("ix_price_bar_symbol_event", "price_bars", ["symbol", "event_time"])
    op.create_index("ix_price_bar_symbol_available", "price_bars", ["symbol", "available_at"])
    op.create_table(
        "fundamental_documents",
        sa.Column("source", sa.String(64), primary_key=True),
        sa.Column("accession_number", sa.String(32), primary_key=True),
        sa.Column("symbol", sa.String(32), sa.ForeignKey("assets.symbol"), nullable=False),
        sa.Column("cik", sa.String(10), nullable=False),
        sa.Column("form", sa.String(32), nullable=False),
        sa.Column("filing_date", sa.String(10), nullable=False),
        sa.Column("report_date", sa.String(10)),
        sa.Column("primary_document", sa.String(255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_fundamental_symbol_available",
        "fundamental_documents",
        ["symbol", "available_at"],
    )
    op.create_index(
        "ix_fundamental_cik_available",
        "fundamental_documents",
        ["cik", "available_at"],
    )
    op.create_table(
        "data_quality_issues",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("acquisition_runs.id"), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("dataset", sa.String(64), nullable=False),
        sa.Column("partition_key", sa.String(64), nullable=False),
        sa.Column("natural_key", sa.String(255)),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("payload", sa.JSON()),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_quality_source_dataset_detected",
        "data_quality_issues",
        ["source", "dataset", "detected_at"],
    )
    op.create_table(
        "ingestion_watermarks",
        sa.Column("source", sa.String(64), primary_key=True),
        sa.Column("dataset", sa.String(64), primary_key=True),
        sa.Column("partition_key", sa.String(64), primary_key=True),
        sa.Column("watermark", sa.DateTime(timezone=True)),
        sa.Column("cursor", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ingestion_watermarks")
    op.drop_index("ix_quality_source_dataset_detected", table_name="data_quality_issues")
    op.drop_table("data_quality_issues")
    op.drop_index("ix_fundamental_cik_available", table_name="fundamental_documents")
    op.drop_index("ix_fundamental_symbol_available", table_name="fundamental_documents")
    op.drop_table("fundamental_documents")
    op.drop_index("ix_price_bar_symbol_available", table_name="price_bars")
    op.drop_index("ix_price_bar_symbol_event", table_name="price_bars")
    op.drop_table("price_bars")
    op.drop_index("ix_raw_partition_available", table_name="raw_records")
    op.drop_table("raw_records")
    op.drop_index("ix_acquisition_source_dataset_started", table_name="acquisition_runs")
    op.drop_table("acquisition_runs")
    op.drop_table("assets")
