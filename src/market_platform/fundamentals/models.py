from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class ParsedFilingFact(BaseModel):
    normalized_metric: str
    source_concept: str
    context_id: str
    period_start: str | None = None
    period_end: str | None = None
    instant: str | None = None
    value_numeric: Decimal | None = None
    value_text: str | None = None
    unit: str | None = None
    decimals: str | None = None
    derived: bool = False
    formula: str | None = None


class ParsedFiling(BaseModel):
    parser_version: str
    taxonomy: str
    basis: Literal["consolidated", "standalone", "unknown"]
    audited: bool | None
    reporting_quarter: str | None
    period_start: str | None
    period_end: str | None
    facts: list[ParsedFilingFact]


class FilingRefreshResult(BaseModel):
    symbol: str
    considered_filings: int
    downloaded_documents: int = 0
    cached_documents: int = 0
    parsed_documents: int = 0
    failed_documents: int = 0
    normalized_facts: int = 0
    warnings: list[str] = Field(default_factory=list)


class FundamentalFact(BaseModel):
    metric: str
    value: float | None
    text_value: str | None
    unit: str | None
    source_concept: str
    derived: bool
    formula: str | None
    evidence_id: str


class FundamentalPeriod(BaseModel):
    document_id: str
    filing_external_id: str
    period_start: str | None
    period_end: str | None
    basis: str
    audited: bool | None
    taxonomy: str
    source_url: str
    available_at: datetime
    revision_number: int
    metrics: list[FundamentalFact]


class FundamentalInsight(BaseModel):
    insight_id: str
    kind: Literal["growth", "profitability", "quality", "risk", "data_quality"]
    severity: Literal["positive", "neutral", "caution"]
    title: str
    detail: str
    evidence_ids: list[str]


class FundamentalSnapshot(BaseModel):
    symbol: str
    generated_at: datetime
    cutoff: datetime
    period_count: int
    latest_period_end: str | None
    latest_basis: str | None
    periods: list[FundamentalPeriod]
    insights: list[FundamentalInsight]
    coverage: dict[str, bool]
    methodology: str
