from __future__ import annotations

from datetime import UTC, date, datetime

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from market_platform.api.app import create_app
from market_platform.bonds.analytics import calculate_bond, interpolate_curve
from market_platform.bonds.models import (
    BondLadderRequest,
    BondSecurity,
    YieldCurvePoint,
)
from market_platform.bonds.providers import PublicBondDataProvider
from market_platform.bonds.service import BondResearchService
from market_platform.db.repository import SqlAlchemyDataRepository


def _repository() -> SqlAlchemyDataRepository:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    repository = SqlAlchemyDataRepository("sqlite+pysqlite:///:memory:", engine=engine)
    repository.create_schema()
    return repository


def _security() -> BondSecurity:
    return BondSecurity(
        isin="INE000000001",
        issuer="Example Infrastructure Limited",
        security_name="8.00% secured NCD 2031",
        coupon_rate_pct=8,
        coupon_frequency=1,
        issue_date=date(2021, 1, 1),
        maturity_date=date(2031, 1, 1),
        face_value=1000,
        issue_price=1000,
        rating="AAA",
        rating_agency="Fixture Ratings",
        secured=True,
        source="fixture",
        source_url="https://example.test/bond",
        available_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _curve() -> list[YieldCurvePoint]:
    return [
        YieldCurvePoint(
            curve_date=date(2026, 1, 1),
            tenor_years=tenor,
            yield_pct=yield_pct,
            source="ccil_zcyc",
            source_url="https://example.test/curve.xls",
            available_at=datetime(2026, 1, 1, 23, 59, tzinfo=UTC),
        )
        for tenor, yield_pct in [(0.5, 5.5), (1, 5.8), (3, 6.2), (5, 6.5), (10, 6.9)]
    ]


def test_bond_analytics_calculate_yield_duration_and_rate_scenarios() -> None:
    calculation = calculate_bond(
        _security(),
        clean_price=1000,
        settlement_date=date(2026, 1, 1),
    )

    assert calculation.current_yield_pct == pytest.approx(8)
    assert calculation.ytm_pct == pytest.approx(8, rel=1e-6)
    assert calculation.modified_duration_years is not None
    assert calculation.dv01 is not None and calculation.dv01 > 0
    assert calculation.scenarios[0].shift_bps == -100
    assert calculation.scenarios[0].price_change_pct > 0
    assert calculation.scenarios[-1].price_change_pct < 0
    assert interpolate_curve(_curve(), 4) == pytest.approx(6.35)


def test_repository_service_ladder_and_api_are_deterministic() -> None:
    repository = _repository()
    repository.save_bond_data(securities=[_security()], curve=_curve())
    service = BondResearchService(repository)

    snapshot = service.snapshot()
    ladder = service.ladder(
        BondLadderRequest(budget=100_000, horizon_years=5, risk_level="medium")
    )

    assert snapshot.curve_date == date(2026, 1, 1)
    assert snapshot.securities[0].isin == "INE000000001"
    assert snapshot.risk[0].rating_band == "high"
    assert snapshot.risk[0].liquidity_status == "metadata_only"
    assert sum(item.amount for item in ladder.buckets) == pytest.approx(100_000)
    assert all(item.tenor_years <= 5 for item in ladder.buckets)

    client = TestClient(create_app(repository=repository))
    overview = client.get("/api/v1/bonds")
    calculation = client.post(
        "/api/v1/bonds/calculate",
        json={"isin": "INE000000001", "clean_price": 1000, "settlement_date": "2026-01-01"},
    )
    proposal = client.post(
        "/api/v1/bonds/ladder",
        json={"budget": 100000, "horizon_years": 5, "risk_level": "low"},
    )
    assert overview.status_code == 200
    assert calculation.status_code == 200
    assert proposal.status_code == 200
    assert calculation.json()["ytm_pct"] == pytest.approx(8)


def test_bond_central_adapter_rejects_expired_and_floating_records() -> None:
    active_record = {
        "isin": "INE000000001",
        "issuer": "STATE BANK OF INDIA",
        "security_name": "8.00% SBI BOND 2031",
        "coupon_rate": 8,
        "frequency": "Once a year",
        "face_value": "1000",
        "issue_price": "1000",
        "maturity_date": "2031-01-01 00:00:00",
        "allotment_date": "2021-01-01 00:00:00",
        "interest_type": "Fixed Interest",
        "security_status": "ACTIVE",
        "ratings": [{"cra_rating": "AAA", "credit_rating_agency_name": "Fixture"}],
        "secured_unsecured": "Unsecured",
    }
    floating_record = {**active_record, "isin": "INE000000002", "interest_type": "Floating"}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/securities/"
        return httpx.Response(
            200,
            json={
                "data": [{"data": active_record}, {"data": floating_record}],
                "pagination_info": {"total_records": 2},
            },
        )

    provider = PublicBondDataProvider(transport=httpx.MockTransport(handler))
    try:
        records = provider.fetch_corporate_bonds(per_issuer=1)
    finally:
        provider.close()

    assert [item.isin for item in records] == ["INE000000001"]
    assert records[0].rating == "AAA"
    assert records[0].secured is False
