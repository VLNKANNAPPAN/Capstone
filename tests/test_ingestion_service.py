from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from market_platform.db.repository import SqlAlchemyDataRepository
from market_platform.domain.models import AcquisitionBatch, Asset, PriceBar, RawRecord
from market_platform.services.ingestion import MarketIngestionService


class RecordingProvider:
    source_name = "fixture"

    def __init__(self) -> None:
        self.starts: list[datetime] = []

    def fetch_bars(
        self,
        *,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str,
    ) -> AcquisitionBatch[PriceBar]:
        self.starts.append(start)
        event_time = datetime(2026, 1, 5, 14, 30, tzinfo=UTC)
        available_at = datetime(2026, 1, 5, 14, 31, tzinfo=UTC)
        bar = PriceBar(
            symbol=symbol,
            timeframe=timeframe,
            event_time=event_time,
            available_at=available_at,
            open=Decimal("100"),
            high=Decimal("102"),
            low=Decimal("99"),
            close=Decimal("101"),
            volume=Decimal("500"),
            source=self.source_name,
        )
        raw = RawRecord(
            source=self.source_name,
            dataset="price_bars",
            natural_key=f"{symbol}:{timeframe}:{event_time.isoformat()}",
            partition_key=symbol,
            payload={"close": 101},
            event_time=event_time,
            available_at=available_at,
        )
        return AcquisitionBatch[PriceBar](
            source=self.source_name,
            dataset="price_bars",
            partition_key=symbol,
            raw_records=[raw],
            records=[bar],
            watermark=available_at,
        )


def _repository() -> SqlAlchemyDataRepository:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    repository = SqlAlchemyDataRepository("sqlite+pysqlite:///:memory:", engine=engine)
    repository.create_schema()
    return repository


def test_ingestion_uses_saved_watermark_on_next_run() -> None:
    repository = _repository()
    provider = RecordingProvider()
    service = MarketIngestionService(provider=provider, repository=repository)
    initial_start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 2, 1, tzinfo=UTC)

    service.ingest(
        asset=Asset(symbol="AAPL"),
        start=initial_start,
        end=end,
        timeframe="1Min",
    )
    service.ingest(
        asset=Asset(symbol="AAPL"),
        start=initial_start,
        end=end,
        timeframe="1Min",
    )

    assert provider.starts == [
        initial_start,
        datetime(2026, 1, 5, 14, 31, tzinfo=UTC),
    ]
