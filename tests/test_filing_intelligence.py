from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from market_platform.api.app import create_app
from market_platform.db.repository import SqlAlchemyDataRepository
from market_platform.domain.models import (
    AcquisitionBatch,
    Asset,
    CorporateDisclosure,
    DisclosureType,
)
from market_platform.fundamentals.service import FilingIntelligenceService, _select_filings
from market_platform.fundamentals.xbrl import XbrlDocumentClient, parse_xbrl

FIXTURE = Path(__file__).parent / "fixtures" / "indian_financial_result.xml"


def _repository() -> SqlAlchemyDataRepository:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    repository = SqlAlchemyDataRepository("sqlite+pysqlite:///:memory:", engine=engine)
    repository.create_schema()
    repository.register_asset(
        Asset(
            symbol="ASIANPAINT.NS",
            name="Asian Paints",
            exchange="NSE",
            currency="INR",
        )
    )
    return repository


def _add_disclosure(repository: SqlAlchemyDataRepository) -> None:
    published = datetime(2025, 2, 4, 8, 6, tzinfo=UTC)
    disclosure = CorporateDisclosure(
        source="nse",
        external_id="INDAS_118658_1370927",
        symbol="ASIANPAINT.NS",
        exchange="NSE",
        disclosure_type=DisclosureType.FINANCIAL_RESULT,
        category="Financial Results",
        headline="Integrated Filing - Financial Results",
        document_url="https://example.test/asianpaint.xml",
        period_end="2024-12-31",
        published_at=published,
        available_at=published,
        metadata={"consolidated": "consolidated"},
    )
    batch = AcquisitionBatch[CorporateDisclosure](
        source="nse",
        dataset="corporate_disclosures",
        partition_key="ASIANPAINT.NS",
        records=[disclosure],
        watermark=published,
    )
    run_id = repository.start_run(
        source="nse", dataset="corporate_disclosures", partition_key="ASIANPAINT.NS"
    )
    repository.save_disclosures_batch(run_id, batch)


def test_xbrl_parser_normalizes_direct_and_derived_facts() -> None:
    parsed = parse_xbrl(FIXTURE.read_text(encoding="utf-8"))
    facts = {fact.normalized_metric: fact for fact in parsed.facts}

    assert parsed.period_end == "2024-12-31"
    assert parsed.basis == "consolidated"
    assert parsed.audited is False
    assert parsed.taxonomy == "https://example.test/ind-as-2024.xsd"
    assert facts["revenue"].value_numeric == Decimal("85494400000")
    assert facts["revenue"].context_id == "OneD"
    assert facts["ebit"].value_numeric == Decimal("14680000000")
    assert facts["ebitda"].value_numeric == Decimal("16580000000")
    assert float(facts["net_margin_pct"].value_numeric or 0) == pytest.approx(12.9889, rel=1e-4)
    assert float(facts["interest_coverage"].value_numeric or 0) == pytest.approx(30.5833, rel=1e-4)
    assert facts["ebitda_margin_pct"].derived is True
    assert facts["ebitda_margin_pct"].formula == "ebitda / revenue * 100"


def test_filing_selection_uses_calendar_dates_not_lexical_dates() -> None:
    available = datetime(2025, 2, 4, 8, 6, tzinfo=UTC)

    def disclosure(external_id: str, period_end: str) -> CorporateDisclosure:
        return CorporateDisclosure(
            source="nse",
            external_id=external_id,
            symbol="ASIANPAINT.NS",
            exchange="NSE",
            disclosure_type=DisclosureType.FINANCIAL_RESULT,
            category="Financial Results",
            headline="Integrated Filing - Financial Results",
            document_url=f"https://example.test/{external_id}.xml",
            period_end=period_end,
            published_at=available,
            available_at=available,
            metadata={"consolidated": "consolidated"},
        )

    selected = _select_filings(
        [disclosure("march", "31-Mar-2024"), disclosure("december", "31-Dec-2024")],
        1,
    )

    assert selected[0].external_id == "december"


def test_refresh_is_idempotent_and_snapshot_is_point_in_time() -> None:
    repository = _repository()
    _add_disclosure(repository)
    xml = FIXTURE.read_bytes()
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=xml, headers={"Content-Type": "application/xml"})

    client = XbrlDocumentClient(transport=httpx.MockTransport(handler), sleep=lambda _: None)
    service = FilingIntelligenceService(repository, client=client)
    try:
        first = service.refresh(symbol="ASIANPAINT.NS")
        second = service.refresh(symbol="ASIANPAINT.NS")
    finally:
        client.close()

    assert first.parsed_documents == 1
    assert first.normalized_facts >= 10
    assert second.parsed_documents == 0
    assert second.cached_documents == 1
    assert calls == 2

    before = service.snapshot(
        symbol="ASIANPAINT.NS", cutoff=datetime(2025, 2, 4, 8, 5, tzinfo=UTC)
    )
    after = service.snapshot(
        symbol="ASIANPAINT.NS", cutoff=datetime(2025, 2, 4, 8, 7, tzinfo=UTC)
    )
    assert before.period_count == 0
    assert after.period_count == 1
    assert after.latest_basis == "consolidated"
    assert after.coverage["margins"] is True
    assert after.coverage["cash_flow"] is False
    assert any(item.title == "Interest coverage" for item in after.insights)

    response = TestClient(create_app(repository=repository)).get(
        "/api/v1/stocks/ASIANPAINT.NS/fundamentals"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["latest_period_end"] == "2024-12-31"
    latest = body["periods"][0]
    assert any(item["evidence_id"].startswith("filing:nse:") for item in latest["metrics"])
