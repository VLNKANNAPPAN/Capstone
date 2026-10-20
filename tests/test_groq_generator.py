from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx

from market_platform.analytics.models import (
    LiquidityMetrics,
    MomentumMetrics,
    ReturnMetrics,
    RiskMetrics,
    TechnicalSnapshot,
    TrendMetrics,
)
from market_platform.research.groq import GroqResearchGenerator
from market_platform.research.models import (
    DataCoverage,
    ExplainResearchRequest,
    ResearchNarrativePayload,
    ResearchSnapshot,
    ScenarioNarrative,
)


def _narrative_payload() -> ResearchNarrativePayload:
    scenario = ScenarioNarrative(
        label="Base case",
        assumptions=["Evidence remains current."],
        interpretation="The view remains conditional.",
    )
    return ResearchNarrativePayload(
        executive_summary="Evidence is mixed and incomplete.",
        what_is_happening="The stored technical regime is mixed.",
        why_it_matters="Risk and momentum differ.",
        supporting_evidence=[],
        contradicting_evidence=[],
        key_risks=["Missing fundamentals"],
        assumptions=["Stored prices are complete"],
        thesis_breakers=["Evidence becomes stale"],
        bull_case=scenario,
        base_case=scenario,
        bear_case=scenario,
        confidence=0.4,
        data_gaps=["fundamentals"],
        disclaimer="Educational research only.",
    )


def _snapshot() -> ResearchSnapshot:
    now = datetime(2026, 9, 26, tzinfo=UTC)
    technical = TechnicalSnapshot(
        symbol="INFY.NS",
        timeframe="1Day",
        cutoff=now,
        as_of=now,
        source="fixture",
        observation_count=252,
        close=1000,
        returns=ReturnMetrics(),
        trend=TrendMetrics(),
        momentum=MomentumMetrics(),
        risk=RiskMetrics(),
        liquidity=LiquidityMetrics(),
        signal="mixed",
        methodology="fixture",
    )
    return ResearchSnapshot(
        symbol="INFY.NS",
        company_name="Infosys",
        exchange="NSE",
        currency="INR",
        generated_at=now,
        cutoff=now,
        technical=technical,
        evidence=[],
        claims=[],
        coverage=DataCoverage(
            price_history=True,
            technical_metrics=True,
            news=False,
            fundamentals=False,
            macro=False,
            social=False,
            missing=["news", "fundamentals", "macro", "social"],
        ),
        methodology="fixture",
    )


def test_groq_generator_uses_server_key_and_structured_output() -> None:
    expected = _narrative_payload()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/openai/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-key"
        body = json.loads(request.content)
        assert body["model"] == "openai/gpt-oss-20b"
        assert body["reasoning_effort"] == "low"
        assert body["include_reasoning"] is False
        assert body["max_completion_tokens"] == 4096
        assert body["response_format"]["type"] == "json_schema"
        assert body["response_format"]["json_schema"]["strict"] is True
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": expected.model_dump_json()}}]},
        )

    generator = GroqResearchGenerator(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )
    try:
        result = generator.generate(
            snapshot=_snapshot(),
            request=ExplainResearchRequest(),
        )
    finally:
        generator.close()

    assert result == expected
