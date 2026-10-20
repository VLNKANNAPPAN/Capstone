from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from market_platform.api.app import create_app
from market_platform.db.repository import SqlAlchemyDataRepository
from market_platform.domain.models import AcquisitionBatch, Asset, PriceBar, RawRecord


def _india_repository() -> SqlAlchemyDataRepository:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    repository = SqlAlchemyDataRepository("sqlite+pysqlite:///:memory:", engine=engine)
    repository.create_schema()
    asset = Asset(
        symbol="RELIANCE.NS",
        name="Reliance Industries",
        exchange="NSE",
        currency="INR",
    )
    repository.register_asset(asset)

    start = datetime(2025, 1, 1, 10, tzinfo=UTC)
    bars: list[PriceBar] = []
    raw_records: list[RawRecord] = []
    for index in range(260):
        event_time = start + timedelta(days=index)
        available_at = event_time + timedelta(hours=6)
        close = Decimal("1000") + Decimal(index) + Decimal(index % 7) / Decimal("10")
        bar = PriceBar(
            symbol=asset.symbol,
            timeframe="1Day",
            event_time=event_time,
            available_at=available_at,
            open=close - Decimal("2"),
            high=close + Decimal("5"),
            low=close - Decimal("6"),
            close=close,
            volume=Decimal("1000000") + Decimal(index * 1000),
            source="fixture_india",
        )
        bars.append(bar)
        raw_records.append(
            RawRecord(
                source="fixture_india",
                dataset="price_bars",
                natural_key=f"{asset.symbol}:1Day:{index}",
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
        source="fixture_india",
        dataset="price_bars",
        partition_key=asset.symbol,
    )
    repository.save_market_batch(run_id, batch)
    return repository


def test_stock_catalog_exposes_indian_asset_metadata() -> None:
    client = TestClient(create_app(repository=_india_repository()))

    response = client.get("/api/v1/stocks")

    assert response.status_code == 200
    assert response.json()[0]["symbol"] == "RELIANCE.NS"
    assert response.json()[0]["exchange"] == "NSE"
    assert response.json()[0]["currency"] == "INR"


def test_technical_endpoint_returns_auditable_point_in_time_metrics() -> None:
    client = TestClient(create_app(repository=_india_repository()))

    response = client.get("/api/v1/stocks/RELIANCE.NS/technical")

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "RELIANCE.NS"
    assert body["source"] == "fixture_india"
    assert body["observation_count"] == 260
    assert body["trend"]["sma_200"] is not None
    assert body["momentum"]["rsi_14"] is not None
    assert body["momentum"]["macd"] is not None
    assert body["risk"]["atr_14"] is not None
    assert body["risk"]["sharpe_252d"] is not None
    assert body["liquidity"]["volume_ratio_20d"] is not None


def test_technical_endpoint_excludes_bars_not_available_at_cutoff() -> None:
    client = TestClient(create_app(repository=_india_repository()))
    cutoff = datetime(2025, 4, 11, 15, 59, tzinfo=UTC)

    response = client.get(
        "/api/v1/stocks/RELIANCE.NS/technical",
        params={"cutoff": cutoff.isoformat()},
    )

    assert response.status_code == 200
    assert response.json()["observation_count"] == 100


def test_technical_endpoint_returns_404_when_history_is_missing() -> None:
    client = TestClient(create_app(repository=_india_repository()))

    response = client.get("/api/v1/stocks/UNKNOWN.NS/technical")

    assert response.status_code == 404
    assert response.json()["detail"] == "no price history found"


def test_metric_history_returns_four_rolling_series() -> None:
    client = TestClient(create_app(repository=_india_repository()))

    response = client.get(
        "/api/v1/stocks/RELIANCE.NS/metric-history",
        params={"window": 60, "step": 10},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "RELIANCE.NS"
    assert body["window"] == 60
    assert len(body["points"]) > 10
    latest = body["points"][-1]
    assert latest["sharpe"] is not None
    assert latest["annualized_volatility_pct"] is not None
    assert latest["maximum_drawdown_pct"] is not None


def test_company_search_and_portfolio_proposal_use_covered_universe() -> None:
    client = TestClient(create_app(repository=_india_repository()))

    search = client.get("/api/v1/companies/search", params={"q": "Reliance"})
    proposal = client.post(
        "/api/v1/portfolio/propose",
        json={"budget": 100000, "risk_level": "balanced", "duration_months": 12},
    )

    assert search.status_code == 200
    assert search.json()[0]["symbol"] == "RELIANCE.NS"
    assert proposal.status_code == 200
    body = proposal.json()
    assert body["holdings"][0]["symbol"] == "RELIANCE.NS"
    assert body["holdings"][0]["sector"] == "Energy & diversified"
    assert body["invested_amount"] <= 100000
    assert body["expectation"]["low_return_pct"] <= body["expectation"]["high_return_pct"]
    assert 0 <= body["expectation"]["confidence_score"] <= 80
    assert body["diversification"]["sector_count"] == 1
    assert len(body["factor_weights_pct"]) == 9
    assert body["ai_narrative"] is None
