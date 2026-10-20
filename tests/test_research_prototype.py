from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from market_platform.api.app import create_app
from market_platform.db.models import ResearchAnalysisRow, ThesisVersionRow
from market_platform.db.repository import SqlAlchemyDataRepository
from market_platform.domain.models import AcquisitionBatch, Asset, PriceBar, RawRecord
from market_platform.research.models import (
    ExplainResearchRequest,
    ResearchNarrativePayload,
    ResearchSnapshot,
    ScenarioNarrative,
    ThesisMetricState,
)
from market_platform.research.service import ResearchExplanationService, ResearchSnapshotService
from market_platform.research.thesis import detect_contradictions, evaluate_breakers


class FixtureNarrativeGenerator:
    model = "fixture-model"

    def generate(
        self,
        *,
        snapshot: ResearchSnapshot,
        request: ExplainResearchRequest,
    ) -> ResearchNarrativePayload:
        assert snapshot.symbol == "TCS.NS"
        assert request.horizon == "long_term"
        return ResearchNarrativePayload(
            executive_summary="The stored price evidence is constructive but incomplete.",
            what_is_happening="Momentum is positive in the supplied snapshot.",
            why_it_matters="Trend and downside risk should be evaluated together.",
            supporting_evidence=[
                {
                    "title": "Positive return",
                    "explanation": "The 60-day return is positive.",
                    "evidence_ids": ["metric:return_60d"],
                }
            ],
            contradicting_evidence=[],
            key_risks=["Fundamentals are unavailable."],
            assumptions=["Stored daily bars are complete."],
            thesis_breakers=["The price falls below its 20-day average."],
            bull_case=ScenarioNarrative(
                label="Bull case",
                assumptions=["Momentum persists."],
                interpretation="The technical regime remains constructive.",
            ),
            base_case=ScenarioNarrative(
                label="Base case",
                assumptions=["Momentum moderates."],
                interpretation="Evidence remains mixed.",
            ),
            bear_case=ScenarioNarrative(
                label="Bear case",
                assumptions=["Downside risk expands."],
                interpretation="The technical claim requires reassessment.",
            ),
            confidence=0.54,
            data_gaps=["fundamentals", "macro", "social", "news"],
            disclaimer="Educational research only; not financial advice.",
        )


def _repository() -> SqlAlchemyDataRepository:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    repository = SqlAlchemyDataRepository("sqlite+pysqlite:///:memory:", engine=engine)
    repository.create_schema()
    asset = Asset(symbol="TCS.NS", name="Tata Consultancy Services", exchange="NSE", currency="INR")
    repository.register_asset(asset)
    start = datetime(2025, 1, 1, 10, tzinfo=UTC)
    bars: list[PriceBar] = []
    raw_records: list[RawRecord] = []
    for index in range(220):
        event_time = start + timedelta(days=index)
        available_at = event_time + timedelta(hours=6)
        close = Decimal("3000") + Decimal(index)
        bars.append(
            PriceBar(
                symbol=asset.symbol,
                timeframe="1Day",
                event_time=event_time,
                available_at=available_at,
                open=close - 2,
                high=close + 5,
                low=close - 5,
                close=close,
                volume=Decimal("500000") + Decimal(index),
                source="fixture_india",
            )
        )
        raw_records.append(
            RawRecord(
                source="fixture_india",
                dataset="price_bars",
                natural_key=f"TCS.NS:1Day:{index}",
                partition_key=asset.symbol,
                payload={"close": str(close)},
                event_time=event_time,
                available_at=available_at,
            )
        )
    batch = AcquisitionBatch[PriceBar](
        source="fixture_india",
        dataset="price_bars",
        partition_key=asset.symbol,
        raw_records=raw_records,
        records=bars,
        watermark=bars[-1].available_at,
    )
    run_id = repository.start_run(
        source="fixture_india", dataset="price_bars", partition_key=asset.symbol
    )
    repository.save_market_batch(run_id, batch)
    return repository


def test_research_snapshot_exposes_evidence_and_missing_sources() -> None:
    client = TestClient(create_app(repository=_repository()))

    response = client.get("/api/v1/research/TCS.NS")

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "TCS.NS"
    assert body["coverage"]["technical_metrics"] is True
    assert body["coverage"]["fundamentals"] is False
    assert "fundamentals" in body["coverage"]["missing"]
    assert {item["evidence_id"] for item in body["evidence"]} >= {
        "metric:return_60d",
        "metric:cvar95",
    }


def test_research_explanation_is_persisted_with_snapshot_provenance() -> None:
    repository = _repository()
    explainer = ResearchExplanationService(
        repository=repository,
        generator=FixtureNarrativeGenerator(),
    )
    client = TestClient(create_app(repository=repository, research_explainer=explainer))

    response = client.post(
        "/api/v1/research/TCS.NS/explain",
        json={"horizon": "long_term", "risk_profile": "balanced"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "fixture-model"
    assert body["snapshot_hash"]
    assert body["narrative"]["supporting_evidence"][0]["evidence_ids"] == ["metric:return_60d"]
    with Session(repository.engine) as session:
        assert session.scalar(select(func.count()).select_from(ResearchAnalysisRow)) == 1


def test_explanation_requires_server_side_groq_configuration() -> None:
    client = TestClient(create_app(repository=_repository()))

    response = client.post("/api/v1/research/TCS.NS/explain", json={})

    assert response.status_code == 503
    assert "GROQ_API_KEY" in response.json()["detail"]


def test_point_in_time_thesis_versions_are_persisted_compared_and_idempotent() -> None:
    repository = _repository()
    client = TestClient(create_app(repository=repository))

    first = client.post(
        "/api/v1/research/TCS.NS/thesis",
        params={"cutoff": "2025-05-31T23:59:59Z"},
    )
    second = client.post(
        "/api/v1/research/TCS.NS/thesis",
        params={"cutoff": "2025-08-01T23:59:59Z"},
    )
    repeated = client.post(
        "/api/v1/research/TCS.NS/thesis",
        params={"cutoff": "2025-08-01T23:59:59Z"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    first_body = first.json()
    second_body = second.json()
    assert second_body["previous_version_id"] == first_body["thesis_id"]
    assert second_body["thesis_id"] == repeated.json()["thesis_id"]
    assert second_body["version_number"] == 2
    assert second_body["breakers"]
    assert second_body["methodology_version"] == "thesis-v2"
    assert second_body["sensitivity"]
    assert second_body["sensitivity"][0]["baseline_confidence"] >= second_body["sensitivity"][0][
        "perturbed_confidence"
    ]
    versions = client.get("/api/v1/research/TCS.NS/thesis/versions").json()
    assert [item["version_number"] for item in versions] == [2, 1]
    evaluation = client.get(
        f"/api/v1/theses/{first_body['thesis_id']}/evaluation"
    )
    assert evaluation.status_code == 200
    evaluation_body = evaluation.json()
    assert evaluation_body["expected_direction"] == "undirected"
    assert evaluation_body["directional_accuracy"] is None
    assert any(item["available"] for item in evaluation_body["outcomes"])
    assert {item["horizon_trading_days"] for item in evaluation_body["outcomes"]} == {
        5,
        20,
        60,
    }
    with Session(repository.engine) as session:
        assert session.scalar(select(func.count()).select_from(ThesisVersionRow)) == 2


def test_machine_testable_breakers_report_declared_thresholds() -> None:
    breakers = evaluate_breakers(
        ThesisMetricState(
            close=100,
            signal="negative trend",
            return_60d_pct=-8,
            distance_sma_20_pct=-2,
            rsi_14=28,
            volatility_30d_pct=31,
            maximum_drawdown_252d_pct=-24,
            sharpe_252d=-0.4,
            cvar_95_daily_pct=-3.4,
        )
    )

    breached = {item.rule_id for item in breakers if item.breached}
    assert breached == {
        "breaker:trend_below_sma20",
        "breaker:momentum_60d_negative",
        "breaker:drawdown_20",
        "breaker:tail_loss_3",
        "breaker:negative_sharpe",
    }


def test_contradiction_detection_flags_positive_return_with_deep_downside_risk() -> None:
    repository = _repository()
    snapshot = ResearchSnapshotService(repository).build(symbol="TCS.NS")
    assert snapshot is not None
    metrics = ThesisMetricState(
        close=3200,
        signal="positive trend",
        return_60d_pct=12,
        distance_sma_20_pct=3,
        rsi_14=62,
        volatility_30d_pct=28,
        maximum_drawdown_252d_pct=-24,
        sharpe_252d=0.8,
        cvar_95_daily_pct=-3.2,
    )

    contradictions = detect_contradictions(snapshot, metrics)

    assert {item.contradiction_id for item in contradictions} == {
        "contradiction:return_risk"
    }
    assert contradictions[0].severity == "high"
