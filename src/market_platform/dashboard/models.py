from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DatasetCounts(BaseModel):
    assets: int = 0
    price_bars: int = 0
    filings: int = 0
    raw_records: int = 0
    quality_issues: int = 0
    news_items: int = 0
    social_items: int = 0
    video_items: int = 0
    corporate_disclosures: int = 0
    macro_observations: int = 0
    bond_securities: int = 0
    yield_curve_points: int = 0


class AssetSummary(BaseModel):
    symbol: str
    name: str | None
    asset_type: str
    exchange: str | None
    currency: str
    cik: str | None
    active: bool


class SourceSummary(BaseModel):
    source: str
    dataset: str
    record_count: int
    latest_available_at: datetime | None
    latest_ingested_at: datetime | None
    latest_run_status: str | None


class RunSummary(BaseModel):
    run_id: str
    source: str
    dataset: str
    partition_key: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    raw_count: int
    accepted_count: int
    rejected_count: int
    error_message: str | None


class QualityIssueSummary(BaseModel):
    issue_id: str
    source: str
    dataset: str
    partition_key: str
    natural_key: str | None
    code: str
    message: str
    severity: str
    detected_at: datetime


class FilingSummary(BaseModel):
    symbol: str
    form: str
    accession_number: str
    filing_date: str
    report_date: str | None
    available_at: datetime
    source_url: str


class LatestPrice(BaseModel):
    symbol: str
    timeframe: str
    event_time: datetime
    available_at: datetime
    close: float
    volume: float
    source: str


class PricePoint(BaseModel):
    event_time: datetime
    available_at: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class PriceSeries(BaseModel):
    symbol: str
    timeframe: str | None
    cutoff: datetime
    points: list[PricePoint] = Field(default_factory=list)


class StockMetric(BaseModel):
    symbol: str
    name: str | None
    currency: str
    as_of: datetime
    close: float
    return_20d_pct: float | None
    return_60d_pct: float | None
    volatility_20d_pct: float | None
    max_drawdown_252d_pct: float | None
    sharpe_252d: float | None
    sortino_252d: float | None
    cvar_95_daily_pct: float | None
    distance_sma20_pct: float | None
    rsi_14: float | None
    average_volume_20d: float | None
    observation_count: int
    signal: str


class MarketBreadth(BaseModel):
    covered_assets: int = 0
    positive_20d: int = 0
    positive_60d: int = 0
    above_sma20: int = 0
    median_return_20d_pct: float | None = None
    median_volatility_20d_pct: float | None = None
    median_sharpe_252d: float | None = None
    median_cvar_95_daily_pct: float | None = None


class MarketAnalytics(BaseModel):
    methodology: str
    breadth: MarketBreadth
    stocks: list[StockMetric] = Field(default_factory=list)


class ContentSummary(BaseModel):
    source: str
    external_id: str
    content_type: str
    title: str
    url: str
    published_at: datetime
    available_at: datetime
    symbols: list[str]
    sentiment_score: float | None


class DashboardSnapshot(BaseModel):
    generated_at: datetime
    latest_ingested_at: datetime | None
    counts: DatasetCounts
    assets: list[AssetSummary] = Field(default_factory=list)
    sources: list[SourceSummary] = Field(default_factory=list)
    latest_prices: list[LatestPrice] = Field(default_factory=list)
    recent_runs: list[RunSummary] = Field(default_factory=list)
    quality_issues: list[QualityIssueSummary] = Field(default_factory=list)
    recent_filings: list[FilingSummary] = Field(default_factory=list)
    market_analytics: MarketAnalytics
    recent_content: list[ContentSummary] = Field(default_factory=list)
