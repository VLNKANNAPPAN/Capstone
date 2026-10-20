from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(UTC)


class AssetType(StrEnum):
    EQUITY = "equity"
    ETF = "etf"
    CRYPTO = "crypto"
    INDEX = "index"


class QualitySeverity(StrEnum):
    WARNING = "warning"
    ERROR = "error"


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ContentType(StrEnum):
    NEWS = "news"
    SOCIAL = "social"
    VIDEO = "video"


class DisclosureType(StrEnum):
    ANNOUNCEMENT = "announcement"
    FINANCIAL_RESULT = "financial_result"


class Asset(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    name: str | None = None
    asset_type: AssetType = AssetType.EQUITY
    exchange: str | None = None
    currency: str = "USD"
    cik: str | None = None
    active: bool = True

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol cannot be empty")
        return normalized

    @field_validator("cik")
    @classmethod
    def normalize_cik(cls, value: str | None) -> str | None:
        if value is None:
            return None
        digits = value.strip()
        if not digits.isdigit() or len(digits) > 10:
            raise ValueError("CIK must contain at most 10 digits")
        return digits.zfill(10)


class RawRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    dataset: str
    natural_key: str
    partition_key: str
    payload: dict[str, Any]
    event_time: datetime | None = None
    available_at: datetime
    ingested_at: datetime = Field(default_factory=utc_now)

    @field_validator("event_time", "available_at", "ingested_at")
    @classmethod
    def validate_time(cls, value: datetime | None) -> datetime | None:
        return None if value is None else ensure_utc(value)


class PriceBar(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    timeframe: str
    event_time: datetime
    available_at: datetime
    ingested_at: datetime = Field(default_factory=utc_now)
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    vwap: Decimal | None = None
    trade_count: int | None = None
    source: str

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("event_time", "available_at", "ingested_at")
    @classmethod
    def validate_time(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @model_validator(mode="after")
    def validate_ohlcv(self) -> PriceBar:
        prices = (self.open, self.high, self.low, self.close)
        if any(price <= 0 for price in prices):
            raise ValueError("OHLC prices must be positive")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be at least open, low, and close")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be at most open, high, and close")
        if self.volume < 0:
            raise ValueError("volume cannot be negative")
        if self.available_at < self.event_time:
            raise ValueError("available_at cannot precede event_time")
        return self


class FundamentalDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    cik: str
    accession_number: str
    form: str
    filing_date: str
    report_date: str | None = None
    primary_document: str
    source_url: str
    event_time: datetime
    available_at: datetime
    ingested_at: datetime = Field(default_factory=utc_now)
    source: str = "sec"

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("cik")
    @classmethod
    def normalize_cik(cls, value: str) -> str:
        if not value.isdigit() or len(value) > 10:
            raise ValueError("CIK must contain at most 10 digits")
        return value.zfill(10)

    @field_validator("event_time", "available_at", "ingested_at")
    @classmethod
    def validate_time(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class ContentItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    external_id: str
    content_type: ContentType
    title: str
    summary: str | None = None
    url: str
    author: str | None = None
    published_at: datetime
    available_at: datetime
    ingested_at: datetime = Field(default_factory=utc_now)
    symbols: list[str] = Field(default_factory=list)
    language: str | None = None
    sentiment_score: float | None = Field(default=None, ge=-1, le=1)
    engagement_score: float | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, value: list[str]) -> list[str]:
        return sorted({symbol.strip().upper() for symbol in value if symbol.strip()})

    @field_validator("published_at", "available_at", "ingested_at")
    @classmethod
    def validate_content_time(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @model_validator(mode="after")
    def validate_availability(self) -> ContentItem:
        if self.available_at < self.published_at:
            raise ValueError("available_at cannot precede published_at")
        return self


class CorporateDisclosure(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    external_id: str
    symbol: str
    exchange: str
    disclosure_type: DisclosureType
    category: str
    headline: str
    summary: str | None = None
    document_url: str | None = None
    period_end: str | None = None
    published_at: datetime
    available_at: datetime
    ingested_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("symbol")
    @classmethod
    def normalize_disclosure_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("published_at", "available_at", "ingested_at")
    @classmethod
    def validate_disclosure_time(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @model_validator(mode="after")
    def validate_disclosure_availability(self) -> CorporateDisclosure:
        if self.available_at < self.published_at:
            raise ValueError("available_at cannot precede published_at")
        return self


class MacroObservation(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    series_id: str
    title: str
    event_time: datetime
    value: Decimal
    unit: str
    frequency: str
    available_at: datetime
    ingested_at: datetime = Field(default_factory=utc_now)
    source_url: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_time", "available_at", "ingested_at")
    @classmethod
    def validate_macro_time(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @model_validator(mode="after")
    def validate_macro_availability(self) -> MacroObservation:
        if self.available_at < self.event_time:
            raise ValueError("available_at cannot precede event_time")
        return self


class DataQualityIssue(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    dataset: str
    partition_key: str
    natural_key: str | None = None
    code: str
    message: str
    severity: QualitySeverity = QualitySeverity.ERROR
    payload: dict[str, Any] | None = None
    detected_at: datetime = Field(default_factory=utc_now)


RecordT = TypeVar(
    "RecordT",
    PriceBar,
    FundamentalDocument,
    ContentItem,
    CorporateDisclosure,
    MacroObservation,
)


class AcquisitionBatch[RecordT](BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    source: str
    dataset: str
    partition_key: str
    raw_records: list[RawRecord] = Field(default_factory=list)
    records: list[RecordT] = Field(default_factory=list)
    issues: list[DataQualityIssue] = Field(default_factory=list)
    watermark: datetime | None = None
    cursor: str | None = None

    @field_validator("watermark")
    @classmethod
    def validate_watermark(cls, value: datetime | None) -> datetime | None:
        return None if value is None else ensure_utc(value)


class IngestionResult(BaseModel):
    run_id: str
    source: str
    dataset: str
    partition_key: str
    raw_count: int
    accepted_count: int
    rejected_count: int
    watermark: datetime | None = None
