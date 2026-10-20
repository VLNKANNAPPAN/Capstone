from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from market_platform.catalog import NseCompanyCatalogService
from market_platform.db.repository import SqlAlchemyDataRepository
from market_platform.domain.models import Asset


class FixtureCatalogProvider:
    def fetch_assets(self) -> list[Asset]:
        return [
            Asset(
                symbol="RELIANCE.NS",
                name="Reliance Industries Limited",
                exchange="NSE",
                currency="INR",
            ),
            Asset(
                symbol="RELINFRA.NS",
                name="Reliance Infrastructure Limited",
                exchange="NSE",
                currency="INR",
            ),
            Asset(
                symbol="TCS.NS",
                name="Tata Consultancy Services Limited",
                exchange="NSE",
                currency="INR",
            ),
        ]


def _repository() -> SqlAlchemyDataRepository:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    repository = SqlAlchemyDataRepository("sqlite+pysqlite:///:memory:", engine=engine)
    repository.create_schema()
    return repository


def test_catalog_search_does_not_register_every_nse_symbol() -> None:
    repository = _repository()
    catalog = NseCompanyCatalogService(
        repository=repository,
        provider=FixtureCatalogProvider(),
    )

    matches = catalog.search("reliance", limit=10)

    assert [asset.symbol for asset in matches] == ["RELIANCE.NS", "RELINFRA.NS"]
    assert repository.list_assets() == []

    selected = catalog.register_selected("tcs")

    assert selected is not None
    assert selected.symbol == "TCS.NS"
    assert [asset.symbol for asset in repository.list_assets()] == ["TCS.NS"]
