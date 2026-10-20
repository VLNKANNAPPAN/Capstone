from __future__ import annotations

from datetime import date, datetime

from market_platform.data.providers.base import (
    ContentProvider,
    CorporateDisclosureProvider,
    DailyMarketFileProvider,
    FundamentalsProvider,
    MacroDataProvider,
    MarketDataProvider,
    VideoContentProvider,
)
from market_platform.db.repository import SqlAlchemyDataRepository
from market_platform.domain.models import Asset, IngestionResult


class MarketIngestionService:
    def __init__(
        self,
        *,
        provider: MarketDataProvider,
        repository: SqlAlchemyDataRepository,
    ) -> None:
        self._provider = provider
        self._repository = repository

    def ingest(
        self,
        *,
        asset: Asset,
        start: datetime,
        end: datetime,
        timeframe: str,
        use_watermark: bool = True,
    ) -> IngestionResult:
        self._repository.register_asset(asset)
        effective_start = start
        if use_watermark:
            watermark, _ = self._repository.get_watermark(
                source=self._provider.source_name,
                dataset="price_bars",
                partition_key=asset.symbol,
            )
            if watermark is not None and watermark > effective_start:
                effective_start = watermark
        run_id = self._repository.start_run(
            source=self._provider.source_name,
            dataset="price_bars",
            partition_key=asset.symbol,
        )
        try:
            batch = self._provider.fetch_bars(
                symbol=asset.symbol,
                start=effective_start,
                end=end,
                timeframe=timeframe,
            )
            return self._repository.save_market_batch(run_id, batch)
        except Exception as exc:
            self._repository.fail_run(run_id, exc)
            raise


class DailyMarketFileIngestionService:
    def __init__(
        self,
        *,
        provider: DailyMarketFileProvider,
        repository: SqlAlchemyDataRepository,
    ) -> None:
        self._provider = provider
        self._repository = repository

    def ingest(
        self,
        *,
        trade_date: date,
        assets: list[Asset],
    ) -> IngestionResult:
        for asset in assets:
            self._repository.register_asset(asset)
        partition_key = trade_date.strftime("%Y%m%d")
        run_id = self._repository.start_run(
            source=self._provider.source_name,
            dataset="price_bars",
            partition_key=partition_key,
        )
        try:
            batch = self._provider.fetch_daily(
                trade_date=trade_date,
                symbols={asset.symbol for asset in assets},
            )
            return self._repository.save_market_batch(run_id, batch)
        except Exception as exc:
            self._repository.fail_run(run_id, exc)
            raise


class FundamentalsIngestionService:
    def __init__(
        self,
        *,
        provider: FundamentalsProvider,
        repository: SqlAlchemyDataRepository,
    ) -> None:
        self._provider = provider
        self._repository = repository

    def ingest(
        self,
        *,
        asset: Asset,
        forms: set[str] | None = None,
    ) -> IngestionResult:
        if asset.cik is None:
            raise ValueError("asset CIK is required for SEC ingestion")
        self._repository.register_asset(asset)
        run_id = self._repository.start_run(
            source=self._provider.source_name,
            dataset="fundamental_documents",
            partition_key=asset.cik,
        )
        try:
            batch = self._provider.fetch_filings(
                symbol=asset.symbol,
                cik=asset.cik,
                forms=forms,
            )
            return self._repository.save_fundamentals_batch(run_id, batch)
        except Exception as exc:
            self._repository.fail_run(run_id, exc)
            raise


class ContentIngestionService:
    def __init__(
        self,
        *,
        provider: ContentProvider,
        repository: SqlAlchemyDataRepository,
    ) -> None:
        self._provider = provider
        self._repository = repository

    def ingest(
        self,
        *,
        symbol: str,
        query: str,
        timespan: str = "1week",
        max_records: int = 50,
    ) -> IngestionResult:
        normalized_symbol = symbol.strip().upper()
        run_id = self._repository.start_run(
            source=self._provider.source_name,
            dataset="content_items",
            partition_key=normalized_symbol,
        )
        try:
            batch = self._provider.fetch_content(
                symbol=normalized_symbol,
                query=query,
                timespan=timespan,
                max_records=max_records,
            )
            return self._repository.save_content_batch(run_id, batch)
        except Exception as exc:
            self._repository.fail_run(run_id, exc)
            raise


class CorporateDisclosureIngestionService:
    def __init__(
        self,
        *,
        provider: CorporateDisclosureProvider,
        repository: SqlAlchemyDataRepository,
    ) -> None:
        self._provider = provider
        self._repository = repository

    def ingest(
        self,
        *,
        asset: Asset,
        start: date,
        end: date,
    ) -> IngestionResult:
        self._repository.register_asset(asset)
        run_id = self._repository.start_run(
            source=self._provider.source_name,
            dataset="corporate_disclosures",
            partition_key=asset.symbol,
        )
        try:
            batch = self._provider.fetch_disclosures(
                symbol=asset.symbol,
                start=start,
                end=end,
            )
            return self._repository.save_disclosures_batch(run_id, batch)
        except Exception as exc:
            self._repository.fail_run(run_id, exc)
            raise


class MacroIngestionService:
    def __init__(
        self,
        *,
        provider: MacroDataProvider,
        repository: SqlAlchemyDataRepository,
    ) -> None:
        self._provider = provider
        self._repository = repository

    def ingest(self, *, history_limit: int = 24) -> IngestionResult:
        run_id = self._repository.start_run(
            source=self._provider.source_name,
            dataset="macro_observations",
            partition_key="india",
        )
        try:
            batch = self._provider.fetch_observations(history_limit=history_limit)
            return self._repository.save_macro_batch(run_id, batch)
        except Exception as exc:
            self._repository.fail_run(run_id, exc)
            raise


class VideoIngestionService:
    def __init__(
        self,
        *,
        provider: VideoContentProvider,
        repository: SqlAlchemyDataRepository,
    ) -> None:
        self._provider = provider
        self._repository = repository

    def ingest(
        self,
        *,
        published_after: datetime,
        max_per_channel: int = 10,
    ) -> IngestionResult:
        run_id = self._repository.start_run(
            source=self._provider.source_name,
            dataset="content_items",
            partition_key="india_youtube",
        )
        try:
            batch = self._provider.fetch_videos(
                published_after=published_after,
                max_per_channel=max_per_channel,
            )
            return self._repository.save_content_batch(run_id, batch)
        except Exception as exc:
            self._repository.fail_run(run_id, exc)
            raise
