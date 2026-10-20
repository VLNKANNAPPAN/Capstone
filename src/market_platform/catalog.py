from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from typing import Protocol

from market_platform.db.repository import SqlAlchemyDataRepository
from market_platform.domain.models import Asset


class AssetCatalogProvider(Protocol):
    def fetch_assets(self) -> list[Asset]: ...


class NseCompanyCatalogService:
    """Searchable NSE symbol metadata without preloading price or content data."""

    def __init__(
        self,
        *,
        repository: SqlAlchemyDataRepository,
        provider: AssetCatalogProvider,
        cache_ttl: timedelta = timedelta(hours=24),
    ) -> None:
        self._repository = repository
        self._provider = provider
        self._cache_ttl = cache_ttl
        self._assets: tuple[Asset, ...] = ()
        self._loaded_at: datetime | None = None
        self._lock = threading.Lock()

    def search(self, query: str, *, limit: int = 20) -> list[Asset]:
        needle = query.strip().casefold()
        if not needle:
            return self._repository.list_assets()[:limit]
        ticker_needle = needle.removesuffix(".ns")
        candidates = [
            asset
            for asset in self._load_catalog()
            if ticker_needle in asset.symbol.removesuffix(".NS").casefold()
            or (asset.name is not None and needle in asset.name.casefold())
        ]
        candidates.sort(key=lambda asset: self._rank(asset, needle, ticker_needle))
        return candidates[:limit]

    def resolve(self, symbol: str) -> Asset | None:
        normalized = _normalize_nse_symbol(symbol)
        existing = self._repository.get_asset(normalized)
        if existing is not None:
            return existing
        return next(
            (asset for asset in self._load_catalog() if asset.symbol == normalized),
            None,
        )

    def register_selected(self, symbol: str) -> Asset | None:
        asset = self.resolve(symbol)
        if asset is not None:
            self._repository.register_asset(asset)
        return asset

    def catalogue_size(self) -> int:
        return len(self._load_catalog())

    def _load_catalog(self) -> tuple[Asset, ...]:
        now = datetime.now(UTC)
        if self._assets and self._loaded_at and now - self._loaded_at < self._cache_ttl:
            return self._assets
        with self._lock:
            now = datetime.now(UTC)
            if self._assets and self._loaded_at and now - self._loaded_at < self._cache_ttl:
                return self._assets
            try:
                fetched = self._provider.fetch_assets()
            except RuntimeError:
                fetched = self._repository.list_assets()
            combined = {asset.symbol: asset for asset in self._repository.list_assets()}
            combined.update({asset.symbol: asset for asset in fetched})
            self._assets = tuple(sorted(combined.values(), key=lambda asset: asset.symbol))
            self._loaded_at = now
            return self._assets

    @staticmethod
    def _rank(asset: Asset, needle: str, ticker_needle: str) -> tuple[int, int, str]:
        ticker = asset.symbol.removesuffix(".NS").casefold()
        name = (asset.name or "").casefold()
        if ticker == ticker_needle:
            tier = 0
        elif ticker.startswith(ticker_needle):
            tier = 1
        elif name.startswith(needle):
            tier = 2
        elif ticker_needle in ticker:
            tier = 3
        elif any(word.startswith(needle) for word in name.split()):
            tier = 4
        else:
            tier = 5
        return (tier, len(name), asset.symbol)


def _normalize_nse_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    return normalized if normalized.endswith(".NS") else f"{normalized}.NS"
