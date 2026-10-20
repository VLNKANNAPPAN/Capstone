from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PortfolioRequest(BaseModel):
    budget: float = Field(gt=0, le=100_000_000)
    risk_level: Literal["conservative", "balanced", "aggressive"] = "balanced"
    duration_months: int = Field(default=12, ge=1, le=120)


class PortfolioHolding(BaseModel):
    symbol: str
    name: str | None
    sector: str
    shares: int
    price: float
    invested_amount: float
    weight_pct: float
    evidence_score: float
    signal: str
    sharpe: float | None
    sortino: float | None
    volatility_pct: float | None
    maximum_drawdown_pct: float | None
    return_60d_pct: float | None
    news_headlines: list[str]
    rationale: str


class PortfolioExpectation(BaseModel):
    horizon_months: int
    low_return_pct: float
    central_return_pct: float
    high_return_pct: float
    low_value: float
    central_value: float
    high_value: float
    confidence_score: int
    confidence_label: str
    observation_count: int
    assumptions: list[str]


class PortfolioDiversification(BaseModel):
    sector_count: int
    sector_allocations_pct: dict[str, float]
    effective_holdings: float
    average_pairwise_correlation: float | None
    maximum_sector_weight_pct: float


class PortfolioNarrative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    allocation_logic: list[str] = Field(min_length=1, max_length=3)
    key_risks: list[str] = Field(min_length=1, max_length=3)
    monitoring_triggers: list[str] = Field(min_length=1, max_length=3)
    disclaimer: str


class PortfolioProposal(BaseModel):
    generated_at: datetime
    budget: float
    invested_amount: float
    cash_remaining: float
    risk_level: str
    duration_months: int
    objective: str
    holdings: list[PortfolioHolding]
    weighted_sharpe: float | None
    weighted_sortino: float | None
    weighted_volatility_pct: float | None
    weighted_maximum_drawdown_pct: float | None
    expectation: PortfolioExpectation
    diversification: PortfolioDiversification
    factor_weights_pct: dict[str, float]
    ai_narrative: PortfolioNarrative | None = None
    warnings: list[str]
    methodology: str
