from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from market_platform.analytics.models import TechnicalSnapshot


class EvidenceItem(BaseModel):
    evidence_id: str
    category: str
    title: str
    detail: str
    direction: Literal["supporting", "contradicting", "neutral", "risk"]
    source_type: str
    source_id: str
    source_url: str | None = None
    observed_at: datetime
    freshness: Literal["fresh", "recent", "aging", "stale"]


class ResearchClaim(BaseModel):
    claim_id: str
    claim_type: str
    claim: str
    evidence_ids: list[str]
    confidence: float = Field(ge=0, le=1)
    status: Literal["supported", "mixed", "caution", "insufficient_data"]


class DataCoverage(BaseModel):
    price_history: bool
    technical_metrics: bool
    news: bool
    fundamentals: bool
    macro: bool
    social: bool
    video: bool = False
    missing: list[str]


class ResearchSnapshot(BaseModel):
    symbol: str
    company_name: str | None
    exchange: str | None
    currency: str
    generated_at: datetime
    cutoff: datetime
    technical: TechnicalSnapshot
    evidence: list[EvidenceItem]
    claims: list[ResearchClaim]
    coverage: DataCoverage
    methodology: str


class ExplainResearchRequest(BaseModel):
    horizon: Literal["short_term", "medium_term", "long_term"] = "medium_term"
    risk_profile: Literal["conservative", "balanced", "aggressive"] = "balanced"


class NarrativeEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    explanation: str
    evidence_ids: list[str]


class ScenarioNarrative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    assumptions: list[str]
    interpretation: str


class ResearchNarrativePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executive_summary: str
    what_is_happening: str
    why_it_matters: str
    supporting_evidence: list[NarrativeEvidence]
    contradicting_evidence: list[NarrativeEvidence]
    key_risks: list[str]
    assumptions: list[str]
    thesis_breakers: list[str]
    bull_case: ScenarioNarrative
    base_case: ScenarioNarrative
    bear_case: ScenarioNarrative
    confidence: float = Field(ge=0, le=1)
    data_gaps: list[str]
    disclaimer: str


class ResearchNarrative(BaseModel):
    analysis_id: str
    symbol: str
    model: str
    prompt_version: str
    snapshot_hash: str
    generated_at: datetime
    narrative: ResearchNarrativePayload


class ThesisMetricState(BaseModel):
    close: float
    signal: str
    return_60d_pct: float | None = None
    distance_sma_20_pct: float | None = None
    rsi_14: float | None = None
    volatility_30d_pct: float | None = None
    maximum_drawdown_252d_pct: float | None = None
    sharpe_252d: float | None = None
    cvar_95_daily_pct: float | None = None


class ThesisBreaker(BaseModel):
    rule_id: str
    label: str
    metric: str
    operator: Literal["lt", "lte", "gt", "gte"]
    threshold: float
    current_value: float | None
    breached: bool
    severity: Literal["monitor", "material", "critical"]
    interpretation: str


class ThesisChange(BaseModel):
    field: str
    label: str
    previous_value: float | str | bool | None
    current_value: float | str | bool | None
    delta: float | None = None
    material: bool
    interpretation: str


class EvidenceContradiction(BaseModel):
    contradiction_id: str
    contradiction_type: str
    severity: Literal["low", "medium", "high"]
    summary: str
    supporting_evidence_ids: list[str]
    contradicting_evidence_ids: list[str]
    interpretation: str


class EvidenceSensitivity(BaseModel):
    scenario_id: str
    removed_category: str
    baseline_confidence: float = Field(ge=0, le=1)
    perturbed_confidence: float = Field(ge=0, le=1)
    confidence_delta: float = Field(ge=0, le=1)
    remaining_evidence_count: int = Field(ge=0)
    fragile: bool
    interpretation: str


class ThesisVersion(BaseModel):
    thesis_id: str
    symbol: str
    version_number: int = Field(ge=1)
    cutoff: datetime
    as_of: datetime
    created_at: datetime
    previous_version_id: str | None
    snapshot_hash: str
    state: Literal["constructive", "neutral", "cautious", "at_risk"]
    confidence: float = Field(ge=0, le=1)
    evidence_coverage_pct: float = Field(ge=0, le=100)
    metrics: ThesisMetricState
    breakers: list[ThesisBreaker]
    changes: list[ThesisChange]
    contradictions: list[EvidenceContradiction] = Field(default_factory=list)
    sensitivity: list[EvidenceSensitivity] = Field(default_factory=list)
    methodology_version: str = "thesis-v1"
    methodology: str


class ThesisOutcomePoint(BaseModel):
    horizon_trading_days: int
    available: bool
    end_date: datetime | None = None
    realized_return_pct: float | None = None
    realized_direction: Literal["positive", "negative", "flat", "unavailable"]
    thesis_aligned: bool | None = None


class ThesisEvaluation(BaseModel):
    thesis_id: str
    symbol: str
    version_number: int
    thesis_cutoff: datetime
    thesis_as_of: datetime
    evaluated_at: datetime
    expected_direction: Literal["positive", "negative", "undirected"]
    outcomes: list[ThesisOutcomePoint]
    scored_horizons: int = Field(ge=0)
    aligned_horizons: int = Field(ge=0)
    directional_accuracy: float | None = Field(default=None, ge=0, le=1)
    methodology: str
