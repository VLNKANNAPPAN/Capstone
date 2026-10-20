from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from market_platform.api.app import create_app
from market_platform.db.repository import SqlAlchemyDataRepository
from market_platform.domain.models import AcquisitionBatch, Asset, PriceBar, RawRecord


def _seeded_repository() -> SqlAlchemyDataRepository:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    repository = SqlAlchemyDataRepository("sqlite+pysqlite:///:memory:", engine=engine)
    repository.create_schema()
    repository.register_asset(Asset(symbol="AAPL", name="Apple Inc.", cik="320193"))
    event_time = datetime(2026, 1, 5, 14, 30, tzinfo=UTC)
    available_at = datetime(2026, 1, 5, 14, 31, tzinfo=UTC)
    bar = PriceBar(
        symbol="AAPL",
        timeframe="1Min",
        event_time=event_time,
        available_at=available_at,
        open=Decimal("100"),
        high=Decimal("102"),
        low=Decimal("99"),
        close=Decimal("101"),
        volume=Decimal("500"),
        source="fixture",
    )
    raw = RawRecord(
        source="fixture",
        dataset="price_bars",
        natural_key="AAPL:1Min:2026-01-05T14:30:00Z",
        partition_key="AAPL",
        payload={"c": 101},
        event_time=event_time,
        available_at=available_at,
    )
    batch = AcquisitionBatch[PriceBar](
        source="fixture",
        dataset="price_bars",
        partition_key="AAPL",
        raw_records=[raw],
        records=[bar],
        watermark=available_at,
    )
    run_id = repository.start_run(source="fixture", dataset="price_bars", partition_key="AAPL")
    repository.save_market_batch(run_id, batch)
    return repository


def test_dashboard_snapshot_exposes_storage_and_ingestion_state() -> None:
    client = TestClient(create_app(repository=_seeded_repository()))

    response = client.get("/api/v1/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body["counts"]["assets"] == 1
    assert body["counts"]["price_bars"] == 1
    assert body["sources"][0]["latest_run_status"] == "succeeded"
    assert body["latest_prices"][0]["symbol"] == "AAPL"


def test_price_endpoint_respects_point_in_time_cutoff() -> None:
    client = TestClient(create_app(repository=_seeded_repository()))

    before = client.get(
        "/api/v1/assets/AAPL/prices",
        params={"cutoff": "2026-01-05T14:30:59Z"},
    )
    after = client.get(
        "/api/v1/assets/AAPL/prices",
        params={"cutoff": "2026-01-05T14:31:00Z"},
    )

    assert before.status_code == 200
    assert before.json()["points"] == []
    assert len(after.json()["points"]) == 1


def test_health_checks_database_connection() -> None:
    client = TestClient(create_app(repository=_seeded_repository()))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "database": "connected"}


def test_dashboard_calculates_transparent_daily_metrics() -> None:
    repository = _seeded_repository()
    repository.register_asset(
        Asset(symbol="RELIANCE.NS", name="Reliance Industries", exchange="NSE", currency="INR")
    )
    start = datetime(2025, 1, 1, 3, 45, tzinfo=UTC)
    bars = []
    raws = []
    for index in range(80):
        event_time = start + timedelta(days=index)
        available_at = event_time + timedelta(hours=6, minutes=30)
        price = Decimal("100") + Decimal(index)
        bars.append(
            PriceBar(
                symbol="RELIANCE.NS",
                timeframe="1Day",
                event_time=event_time,
                available_at=available_at,
                open=price,
                high=price + 1,
                low=price - 1,
                close=price,
                volume=Decimal("1000") + Decimal(index),
                source="fixture",
            )
        )
        raws.append(
            RawRecord(
                source="fixture",
                dataset="price_bars",
                natural_key=f"RELIANCE.NS:1Day:{index}",
                partition_key="RELIANCE.NS",
                payload={"close": str(price)},
                event_time=event_time,
                available_at=available_at,
            )
        )
    batch = AcquisitionBatch[PriceBar](
        source="fixture",
        dataset="price_bars",
        partition_key="RELIANCE.NS",
        raw_records=raws,
        records=bars,
        watermark=bars[-1].available_at,
    )
    run_id = repository.start_run(
        source="fixture", dataset="price_bars", partition_key="RELIANCE.NS"
    )
    repository.save_market_batch(run_id, batch)

    body = TestClient(create_app(repository=repository)).get("/api/v1/dashboard").json()
    metric = next(
        item for item in body["market_analytics"]["stocks"] if item["symbol"] == "RELIANCE.NS"
    )
    assert metric["return_20d_pct"] > 0
    assert metric["distance_sma20_pct"] > 0
    assert metric["sharpe_252d"] is not None
    assert metric["sortino_252d"] is None
    assert metric["cvar_95_daily_pct"] is not None
    assert metric["max_drawdown_252d_pct"] == 0
    assert metric["signal"] in {"positive trend", "extended"}
