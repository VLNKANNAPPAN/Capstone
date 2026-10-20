from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

BondType = Literal["corporate", "government", "treasury_bill", "sdl"]


class BondSecurity(BaseModel):
    isin: str
    issuer: str
    security_name: str
    bond_type: BondType = "corporate"
    coupon_rate_pct: float | None = None
    coupon_frequency: int = 1
    issue_date: date | None = None
    maturity_date: date
    face_value: float
    issue_price: float | None = None
    rating: str | None = None
    rating_agency: str | None = None
    rating_outlook: str | None = None
    secured: bool | None = None
    seniority: str | None = None
    callable: bool = False
    puttable: bool = False
    sector: str | None = None
    status: str = "ACTIVE"
    source: str
    source_url: str
    available_at: datetime

    @field_validator("isin")
    @classmethod
    def normalize_isin(cls, value: str) -> str:
        return value.strip().upper()


class YieldCurvePoint(BaseModel):
    curve_date: date
    tenor_years: float
    yield_pct: float
    source: str
    source_url: str
    available_at: datetime


class BondRefreshResult(BaseModel):
    curve_points: int = 0
    securities: int = 0
    source_date: date | None = None
    warnings: list[str] = Field(default_factory=list)


class BondRiskSummary(BaseModel):
    isin: str
    years_to_maturity: float
    annual_coupon_amount: float | None
    benchmark_yield_pct: float | None
    coupon_minus_benchmark_pct: float | None
    rating_band: Literal["sovereign", "high", "medium", "low", "unrated"]
    liquidity_status: Literal["unknown", "metadata_only", "traded", "model_valued"]
    risk_flags: list[str]


class BondUniverseSnapshot(BaseModel):
    generated_at: datetime
    curve_date: date | None
    curve: list[YieldCurvePoint]
    securities: list[BondSecurity]
    risk: list[BondRiskSummary]
    source_notes: list[str]
    methodology: str


class BondCalculationRequest(BaseModel):
    isin: str
    clean_price: float = Field(gt=0)
    settlement_date: date | None = None


class BondRateScenario(BaseModel):
    shift_bps: int
    repriced_clean_price: float
    price_change_pct: float


class BondCalculation(BaseModel):
    isin: str
    settlement_date: date
    clean_price: float
    current_yield_pct: float | None
    ytm_pct: float | None
    macaulay_duration_years: float | None
    modified_duration_years: float | None
    convexity: float | None
    dv01: float | None
    accrued_interest_included: bool = False
    scenarios: list[BondRateScenario]
    warnings: list[str]
    methodology: str


class BondLadderRequest(BaseModel):
    budget: float = Field(ge=10_000, le=100_000_000)
    horizon_years: int = Field(ge=1, le=30)
    risk_level: Literal["low", "medium", "high"] = "low"


class BondLadderBucket(BaseModel):
    label: str
    tenor_years: float
    allocation_pct: float
    amount: float
    indicative_yield_pct: float
    duration_proxy_years: float


class BondLadderProposal(BaseModel):
    generated_at: datetime
    budget: float
    horizon_years: int
    risk_level: str
    curve_date: date
    buckets: list[BondLadderBucket]
    weighted_indicative_yield_pct: float
    weighted_duration_proxy_years: float
    warnings: list[str]
    methodology: str
