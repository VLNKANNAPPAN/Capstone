from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AssetRow(Base):
    __tablename__ = "assets"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255))
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    exchange: Mapped[str | None] = mapped_column(String(64))
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    cik: Mapped[str | None] = mapped_column(String(10), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RawRecordRow(Base):
    __tablename__ = "raw_records"
    __table_args__ = (
        UniqueConstraint(
            "source", "dataset", "natural_key", "checksum", name="uq_raw_record_revision"
        ),
        Index("ix_raw_partition_available", "source", "dataset", "partition_key", "available_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset: Mapped[str] = mapped_column(String(64), nullable=False)
    natural_key: Mapped[str] = mapped_column(String(255), nullable=False)
    partition_key: Mapped[str] = mapped_column(String(64), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    event_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PriceBarRow(Base):
    __tablename__ = "price_bars"
    __table_args__ = (
        Index("ix_price_bar_symbol_event", "symbol", "event_time"),
        Index("ix_price_bar_symbol_available", "symbol", "available_at"),
    )

    symbol: Mapped[str] = mapped_column(ForeignKey("assets.symbol"), primary_key=True)
    timeframe: Mapped[str] = mapped_column(String(16), primary_key=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    source: Mapped[str] = mapped_column(String(64), primary_key=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    vwap: Mapped[Decimal | None] = mapped_column(Numeric(24, 10))
    trade_count: Mapped[int | None] = mapped_column(Integer)


class FundamentalDocumentRow(Base):
    __tablename__ = "fundamental_documents"
    __table_args__ = (
        Index("ix_fundamental_symbol_available", "symbol", "available_at"),
        Index("ix_fundamental_cik_available", "cik", "available_at"),
    )

    source: Mapped[str] = mapped_column(String(64), primary_key=True)
    accession_number: Mapped[str] = mapped_column(String(32), primary_key=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("assets.symbol"), nullable=False)
    cik: Mapped[str] = mapped_column(String(10), nullable=False)
    form: Mapped[str] = mapped_column(String(32), nullable=False)
    filing_date: Mapped[str] = mapped_column(String(10), nullable=False)
    report_date: Mapped[str | None] = mapped_column(String(10))
    primary_document: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ContentItemRow(Base):
    __tablename__ = "content_items"
    __table_args__ = (
        Index("ix_content_type_published", "content_type", "published_at"),
        Index("ix_content_available", "available_at"),
    )

    source: Mapped[str] = mapped_column(String(64), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    content_type: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str | None] = mapped_column(String(255))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    symbols: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    language: Mapped[str | None] = mapped_column(String(32))
    sentiment_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    engagement_score: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    item_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False)


class CorporateDisclosureRow(Base):
    __tablename__ = "corporate_disclosures"
    __table_args__ = (
        Index("ix_disclosure_symbol_published", "symbol", "published_at"),
        Index("ix_disclosure_type_available", "disclosure_type", "available_at"),
    )

    source: Mapped[str] = mapped_column(String(64), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("assets.symbol"), nullable=False)
    exchange: Mapped[str] = mapped_column(String(16), nullable=False)
    disclosure_type: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str] = mapped_column(String(255), nullable=False)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    document_url: Mapped[str | None] = mapped_column(Text)
    period_end: Mapped[str | None] = mapped_column(String(10))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    disclosure_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False)


class MacroObservationRow(Base):
    __tablename__ = "macro_observations"
    __table_args__ = (
        Index("ix_macro_series_event", "series_id", "event_time"),
        Index("ix_macro_available", "available_at"),
    )

    source: Mapped[str] = mapped_column(String(64), primary_key=True)
    series_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(30, 10), nullable=False)
    unit: Mapped[str] = mapped_column(String(64), nullable=False)
    frequency: Mapped[str] = mapped_column(String(64), nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    observation_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSON, nullable=False
    )


class DataQualityIssueRow(Base):
    __tablename__ = "data_quality_issues"
    __table_args__ = (
        Index("ix_quality_source_dataset_detected", "source", "dataset", "detected_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("acquisition_runs.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset: Mapped[str] = mapped_column(String(64), nullable=False)
    partition_key: Mapped[str] = mapped_column(String(64), nullable=False)
    natural_key: Mapped[str | None] = mapped_column(String(255))
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    payload: Mapped[dict[str, object] | None] = mapped_column(JSON)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AcquisitionRunRow(Base):
    __tablename__ = "acquisition_runs"
    __table_args__ = (
        Index("ix_acquisition_source_dataset_started", "source", "dataset", "started_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset: Mapped[str] = mapped_column(String(64), nullable=False)
    partition_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accepted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)


class IngestionWatermarkRow(Base):
    __tablename__ = "ingestion_watermarks"

    source: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset: Mapped[str] = mapped_column(String(64), primary_key=True)
    partition_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    watermark: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cursor: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ResearchAnalysisRow(Base):
    __tablename__ = "research_analyses"
    __table_args__ = (Index("ix_research_analysis_symbol_created", "symbol", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("assets.symbol"), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    response_payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ThesisVersionRow(Base):
    """Immutable, point-in-time thesis state used for replay and change auditing."""

    __tablename__ = "thesis_versions"
    __table_args__ = (
        UniqueConstraint("symbol", "snapshot_hash", name="uq_thesis_symbol_snapshot"),
        Index("ix_thesis_symbol_cutoff", "symbol", "cutoff"),
        Index("ix_thesis_symbol_created", "symbol", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("assets.symbol"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    previous_version_id: Mapped[str | None] = mapped_column(String(36))
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FilingDocumentRow(Base):
    __tablename__ = "filing_documents"
    __table_args__ = (
        UniqueConstraint(
            "source", "filing_external_id", "checksum", name="uq_filing_document_revision"
        ),
        Index("ix_filing_document_symbol_available", "symbol", "available_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    filing_external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    symbol: Mapped[str] = mapped_column(ForeignKey("assets.symbol"), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_size: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    parser_version: Mapped[str] = mapped_column(String(32), nullable=False)
    taxonomy: Mapped[str] = mapped_column(String(255), nullable=False)
    basis: Mapped[str] = mapped_column(String(16), nullable=False)
    audited: Mapped[bool | None] = mapped_column(Boolean)
    reporting_quarter: Mapped[str | None] = mapped_column(String(64))
    period_start: Mapped[str | None] = mapped_column(String(10))
    period_end: Mapped[str | None] = mapped_column(String(10))
    parse_status: Mapped[str] = mapped_column(String(16), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FilingFactRow(Base):
    __tablename__ = "filing_facts"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "normalized_metric", "context_id", name="uq_filing_fact_metric_context"
        ),
        Index("ix_filing_fact_symbol_period", "symbol", "period_end"),
        Index("ix_filing_fact_metric_available", "normalized_metric", "available_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("filing_documents.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(ForeignKey("assets.symbol"), nullable=False)
    normalized_metric: Mapped[str] = mapped_column(String(96), nullable=False)
    source_concept: Mapped[str] = mapped_column(String(255), nullable=False)
    context_id: Mapped[str] = mapped_column(String(128), nullable=False)
    period_start: Mapped[str | None] = mapped_column(String(10))
    period_end: Mapped[str | None] = mapped_column(String(10))
    instant: Mapped[str | None] = mapped_column(String(10))
    value_numeric: Mapped[Decimal | None] = mapped_column(Numeric(36, 8))
    value_text: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(String(64))
    decimals: Mapped[str | None] = mapped_column(String(32))
    derived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    formula: Mapped[str | None] = mapped_column(Text)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BondSecurityRow(Base):
    __tablename__ = "bond_securities"
    __table_args__ = (
        Index("ix_bond_issuer_maturity", "issuer", "maturity_date"),
        Index("ix_bond_rating_maturity", "rating", "maturity_date"),
    )

    isin: Mapped[str] = mapped_column(String(16), primary_key=True)
    issuer: Mapped[str] = mapped_column(String(255), nullable=False)
    security_name: Mapped[str] = mapped_column(Text, nullable=False)
    bond_type: Mapped[str] = mapped_column(String(32), nullable=False)
    coupon_rate_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    coupon_frequency: Mapped[int] = mapped_column(Integer, nullable=False)
    issue_date: Mapped[date | None] = mapped_column(Date)
    maturity_date: Mapped[date] = mapped_column(Date, nullable=False)
    face_value: Mapped[Decimal] = mapped_column(Numeric(24, 4), nullable=False)
    issue_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    rating: Mapped[str | None] = mapped_column(String(64))
    rating_agency: Mapped[str | None] = mapped_column(String(255))
    rating_outlook: Mapped[str | None] = mapped_column(String(64))
    secured: Mapped[bool | None] = mapped_column(Boolean)
    seniority: Mapped[str | None] = mapped_column(String(128))
    callable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    puttable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sector: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class YieldCurvePointRow(Base):
    __tablename__ = "yield_curve_points"
    __table_args__ = (
        Index("ix_yield_curve_date_tenor", "curve_date", "tenor_years"),
    )

    source: Mapped[str] = mapped_column(String(64), primary_key=True)
    curve_date: Mapped[date] = mapped_column(Date, primary_key=True)
    tenor_years: Mapped[Decimal] = mapped_column(Numeric(12, 6), primary_key=True)
    yield_pct: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
