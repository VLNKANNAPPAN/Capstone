from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from market_platform.db.repository import SqlAlchemyDataRepository
from market_platform.domain.models import (
    AcquisitionBatch,
    Asset,
    FundamentalDocument,
    PriceBar,
    RawRecord,
)


def _repository() -> SqlAlchemyDataRepository:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    repository = SqlAlchemyDataRepository("sqlite+pysqlite:///:memory:", engine=engine)
    repository.create_schema()
    repository.register_asset(Asset(symbol="AAPL", cik="320193"))
    return repository


def _bar(event_minute: int, available_minute: int) -> PriceBar:
    return PriceBar(
        symbol="AAPL",
        timeframe="1Min",
        event_time=datetime(2026, 1, 5, 14, event_minute, tzinfo=UTC),
        available_at=datetime(2026, 1, 5, 14, available_minute, tzinfo=UTC),
        ingested_at=datetime(2026, 2, 1, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("102"),
        low=Decimal("99"),
        close=Decimal("101"),
        volume=Decimal("500"),
        source="alpaca",
    )


def test_repository_excludes_future_available_data() -> None:
    repository = _repository()
    records = [_bar(30, 31), _bar(31, 32)]
    raw_records = [
        RawRecord(
            source="alpaca",
            dataset="price_bars",
            natural_key=f"AAPL:1Min:{record.event_time.isoformat()}",
            partition_key="AAPL",
            payload={"index": index},
            event_time=record.event_time,
            available_at=record.available_at,
            ingested_at=record.ingested_at,
        )
        for index, record in enumerate(records)
    ]
    batch = AcquisitionBatch[PriceBar](
        source="alpaca",
        dataset="price_bars",
        partition_key="AAPL",
        records=records,
        raw_records=raw_records,
        watermark=records[-1].available_at,
    )
    run_id = repository.start_run(source="alpaca", dataset="price_bars", partition_key="AAPL")
    repository.save_market_batch(run_id, batch)

    visible = repository.list_price_bars_as_of(
        symbol="AAPL",
        cutoff=datetime(2026, 1, 5, 14, 31, 30, tzinfo=UTC),
        timeframe="1Min",
    )

    assert len(visible) == 1
    assert visible[0].event_time.minute == 30


def test_reingestion_is_idempotent() -> None:
    repository = _repository()
    record = _bar(30, 31)
    raw = RawRecord(
        source="alpaca",
        dataset="price_bars",
        natural_key="AAPL:1Min:2026-01-05T14:30:00Z",
        partition_key="AAPL",
        payload={"t": "2026-01-05T14:30:00Z", "c": 101},
        event_time=record.event_time,
        available_at=record.available_at,
        ingested_at=record.ingested_at,
    )
    batch = AcquisitionBatch[PriceBar](
        source="alpaca",
        dataset="price_bars",
        partition_key="AAPL",
        records=[record],
        raw_records=[raw],
        watermark=record.available_at,
    )
    for _ in range(2):
        run_id = repository.start_run(source="alpaca", dataset="price_bars", partition_key="AAPL")
        repository.save_market_batch(run_id, batch)

    visible = repository.list_price_bars_as_of(
        symbol="AAPL", cutoff=datetime(2026, 1, 6, tzinfo=UTC)
    )
    assert len(visible) == 1


def test_repository_excludes_filing_published_after_cutoff() -> None:
    repository = _repository()
    accepted_at = datetime(2026, 1, 30, 16, 10, tzinfo=UTC)
    document = FundamentalDocument(
        symbol="AAPL",
        cik="320193",
        accession_number="0000320193-26-000001",
        form="10-Q",
        filing_date="2026-01-30",
        report_date="2025-12-27",
        primary_document="aapl-20251227.htm",
        source_url="https://www.sec.gov/example",
        event_time=accepted_at,
        available_at=accepted_at,
        ingested_at=datetime(2026, 2, 1, tzinfo=UTC),
    )
    raw = RawRecord(
        source="sec",
        dataset="fundamental_documents",
        natural_key=document.accession_number,
        partition_key=document.cik,
        payload={"form": "10-Q"},
        event_time=accepted_at,
        available_at=accepted_at,
        ingested_at=document.ingested_at,
    )
    batch = AcquisitionBatch[FundamentalDocument](
        source="sec",
        dataset="fundamental_documents",
        partition_key=document.cik,
        records=[document],
        raw_records=[raw],
        watermark=accepted_at,
    )
    run_id = repository.start_run(
        source="sec", dataset="fundamental_documents", partition_key=document.cik
    )
    repository.save_fundamentals_batch(run_id, batch)

    before_publication = repository.list_fundamentals_as_of(
        symbol="AAPL", cutoff=datetime(2026, 1, 30, 16, 9, 59, tzinfo=UTC)
    )
    after_publication = repository.list_fundamentals_as_of(
        symbol="AAPL", cutoff=datetime(2026, 1, 30, 16, 10, tzinfo=UTC)
    )

    assert before_publication == []
    assert len(after_publication) == 1
