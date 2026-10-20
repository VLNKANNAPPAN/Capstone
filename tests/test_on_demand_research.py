from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from market_platform.catalog import NseCompanyCatalogService
from market_platform.db.repository import SqlAlchemyDataRepository
from market_platform.domain.models import (
    AcquisitionBatch,
    Asset,
    ContentItem,
    ContentType,
    PriceBar,
)
from market_platform.research.on_demand import OnDemandResearchService


class FixtureCatalogProvider:
    def fetch_assets(self) -> list[Asset]:
        return [
            Asset(
                symbol="NEWCO.NS",
                name="New Company Limited",
                exchange="NSE",
                currency="INR",
            )
        ]


class FixtureYahooProvider:
    source_name = "yahoo_research"

    def __init__(self, **_: Any) -> None:
        pass

    def close(self) -> None:
        pass

    def fetch_bars(
        self,
        *,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str,
    ) -> AcquisitionBatch[PriceBar]:
        del start
        bars = []
        first = end - timedelta(days=301)
        for index in range(300):
            event_time = first + timedelta(days=index)
            price = Decimal("100") + Decimal(index) / Decimal("10")
            bars.append(
                PriceBar(
                    symbol=symbol,
                    timeframe=timeframe,
                    event_time=event_time,
                    available_at=event_time + timedelta(hours=6),
                    open=price,
                    high=price + 1,
                    low=price - 1,
                    close=price,
                    volume=Decimal("100000"),
                    source=self.source_name,
                )
            )
        return AcquisitionBatch[PriceBar](
            source=self.source_name,
            dataset="price_bars",
            partition_key=symbol,
            records=bars,
            watermark=bars[-1].available_at,
        )


class FixtureNewsProvider:
    source_name = "google_news_rss"

    def __init__(self, **_: Any) -> None:
        pass

    def close(self) -> None:
        pass

    def fetch_content(
        self,
        *,
        symbol: str,
        query: str,
        timespan: str,
        max_records: int,
    ) -> AcquisitionBatch[ContentItem]:
        assert "New Company Limited" in query
        del timespan, max_records
        now = datetime.now(UTC) - timedelta(minutes=1)
        item = ContentItem(
            source=self.source_name,
            external_id="news-1",
            content_type=ContentType.NEWS,
            title="New Company wins a large order",
            url="https://example.com/new-company-order",
            published_at=now,
            available_at=now,
            ingested_at=now,
            symbols=[symbol],
            language="en-IN",
        )
        return AcquisitionBatch[ContentItem](
            source=self.source_name,
            dataset="content_items",
            partition_key=symbol,
            records=[item],
            watermark=now,
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


def test_uncached_catalog_company_is_acquired_only_after_selection(monkeypatch: Any) -> None:
    repository = _repository()
    catalog = NseCompanyCatalogService(
        repository=repository,
        provider=FixtureCatalogProvider(),
    )
    monkeypatch.setattr(
        "market_platform.research.on_demand.YahooResearchDataProvider",
        FixtureYahooProvider,
    )
    monkeypatch.setattr(
        "market_platform.research.on_demand.GoogleNewsRssProvider",
        FixtureNewsProvider,
    )
    service = OnDemandResearchService(
        repository=repository,
        catalog=catalog,
        yahoo_base_url="https://example.test",
        google_news_base_url="https://example.test",
    )

    assert repository.list_assets() == []
    snapshot = service.prepare(symbol="NEWCO", refresh_news=True)

    assert snapshot.symbol == "NEWCO.NS"
    assert snapshot.technical.observation_count == 300
    assert snapshot.coverage.news is True
    assert repository.get_asset("NEWCO.NS") is not None
