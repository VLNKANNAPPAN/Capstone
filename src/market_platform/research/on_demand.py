from __future__ import annotations

from datetime import UTC, datetime, timedelta

from market_platform.catalog import NseCompanyCatalogService
from market_platform.data.entity_linking import IndiaEquityEntityLinker
from market_platform.data.providers.google_news import GoogleNewsRssProvider
from market_platform.data.providers.yahoo import YahooResearchDataProvider
from market_platform.db.repository import SqlAlchemyDataRepository
from market_platform.domain.models import ContentType
from market_platform.research.models import ResearchSnapshot
from market_platform.research.service import ResearchSnapshotService
from market_platform.services.ingestion import ContentIngestionService, MarketIngestionService


class OnDemandResearchService:
    """Acquire only the selected company's history and recent linked news."""

    def __init__(
        self,
        *,
        repository: SqlAlchemyDataRepository,
        catalog: NseCompanyCatalogService,
        yahoo_base_url: str,
        google_news_base_url: str,
        timeout_seconds: float = 20,
        max_retries: int = 3,
        history_days: int = 800,
        minimum_observations: int = 260,
        news_refresh_after: timedelta = timedelta(hours=6),
    ) -> None:
        self._repository = repository
        self._catalog = catalog
        self._yahoo_base_url = yahoo_base_url
        self._google_news_base_url = google_news_base_url
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._history_days = history_days
        self._minimum_observations = minimum_observations
        self._news_refresh_after = news_refresh_after
        self._research = ResearchSnapshotService(repository)

    def prepare(
        self,
        *,
        symbol: str,
        refresh_news: bool = True,
    ) -> ResearchSnapshot:
        asset = self._catalog.register_selected(symbol)
        if asset is None:
            raise ValueError("symbol is not present in the current NSE equity catalogue")
        now = datetime.now(UTC)
        bars = self._repository.list_price_bars_as_of(
            symbol=asset.symbol,
            cutoff=now,
            timeframe="1Day",
        )
        needs_history = len(bars) < self._minimum_observations
        needs_refresh = not bars or bars[-1].event_time < now - timedelta(days=7)
        if needs_history or needs_refresh:
            start = now - timedelta(days=self._history_days)
            if not needs_history and bars:
                start = bars[-1].event_time - timedelta(days=7)
            market_provider = YahooResearchDataProvider(
                base_url=self._yahoo_base_url,
                timeout_seconds=self._timeout_seconds,
                max_retries=self._max_retries,
            )
            try:
                try:
                    MarketIngestionService(
                        provider=market_provider,
                        repository=self._repository,
                    ).ingest(
                        asset=asset,
                        start=start,
                        end=now + timedelta(days=1),
                        timeframe="1Day",
                        use_watermark=False,
                    )
                except (RuntimeError, ValueError):
                    if not bars:
                        raise
            finally:
                market_provider.close()

        if refresh_news and self._news_is_stale(asset.symbol, now):
            news_provider = GoogleNewsRssProvider(
                entity_linker=IndiaEquityEntityLinker((asset,)),
                base_url=self._google_news_base_url,
                timeout_seconds=self._timeout_seconds,
                max_retries=self._max_retries,
            )
            query_name = asset.name or asset.symbol.removesuffix(".NS")
            ticker = asset.symbol.removesuffix(".NS")
            try:
                try:
                    ContentIngestionService(
                        provider=news_provider,
                        repository=self._repository,
                    ).ingest(
                        symbol=asset.symbol,
                        query=f'"{query_name}" OR "{ticker}" stock NSE',
                        timespan="1week",
                        max_records=30,
                    )
                except (RuntimeError, ValueError):
                    # News is contextual evidence. Its provider failing must not hide
                    # otherwise valid deterministic research data.
                    pass
            finally:
                news_provider.close()

        snapshot = self._research.build(symbol=asset.symbol)
        if snapshot is None:
            raise ValueError("price history could not be prepared for this NSE symbol")
        return snapshot

    def _news_is_stale(self, symbol: str, now: datetime) -> bool:
        content = self._repository.list_content_as_of(
            symbol=symbol,
            cutoff=now,
            limit=100,
        )
        google_news = [
            item
            for item in content
            if item.content_type == ContentType.NEWS and item.source == "google_news_rss"
        ]
        return not google_news or max(item.ingested_at for item in google_news) < (
            now - self._news_refresh_after
        )
