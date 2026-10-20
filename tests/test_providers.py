from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from market_platform.data.providers.alpaca import AlpacaMarketDataProvider
from market_platform.data.providers.gdelt import GdeltNewsProvider
from market_platform.data.providers.sec import SecFundamentalsProvider
from market_platform.data.providers.yahoo import YahooResearchDataProvider


def test_alpaca_provider_normalizes_fixture(fixture_json: Any) -> None:
    payload = fixture_json("alpaca_bars.json")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["APCA-API-KEY-ID"] == "test-key"
        return httpx.Response(200, json=payload)

    provider = AlpacaMarketDataProvider(
        api_key="test-key",
        api_secret="test-secret",
        transport=httpx.MockTransport(handler),
    )
    try:
        batch = provider.fetch_bars(
            symbol="AAPL",
            start=datetime(2026, 1, 5, tzinfo=UTC),
            end=datetime(2026, 1, 6, tzinfo=UTC),
            timeframe="1Min",
        )
    finally:
        provider.close()

    assert len(batch.records) == 2
    assert len(batch.raw_records) == 2
    assert not batch.issues


def test_sec_provider_filters_forms(fixture_json: Any) -> None:
    payload = fixture_json("sec_submissions.json")

    def handler(request: httpx.Request) -> httpx.Response:
        assert "student@example.edu" in request.headers["User-Agent"]
        return httpx.Response(200, json=payload)

    provider = SecFundamentalsProvider(
        user_agent="Capstone student@example.edu",
        transport=httpx.MockTransport(handler),
    )
    try:
        batch = provider.fetch_filings(symbol="AAPL", cik="320193", forms={"10-Q"})
    finally:
        provider.close()

    assert len(batch.records) == 1
    assert batch.records[0].form == "10-Q"
    assert batch.records[0].accession_number == "0000320193-26-000001"


def test_yahoo_provider_normalizes_daily_chart() -> None:
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [1704080700, 1704167100],
                    "indicators": {
                        "quote": [
                            {
                                "open": [100.0, 101.0],
                                "high": [103.0, 104.0],
                                "low": [99.0, 100.0],
                                "close": [102.0, 103.0],
                                "volume": [1000, 1200],
                            }
                        ]
                    },
                }
            ]
        }
    }

    provider = YahooResearchDataProvider(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    )
    try:
        batch = provider.fetch_bars(
            symbol="RELIANCE.NS",
            start=datetime(2024, 1, 1, tzinfo=UTC),
            end=datetime(2024, 1, 3, tzinfo=UTC),
            timeframe="1Day",
        )
    finally:
        provider.close()

    assert len(batch.records) == 2
    assert batch.records[0].symbol == "RELIANCE.NS"
    assert batch.records[0].available_at > batch.records[0].event_time


def test_gdelt_provider_preserves_article_provenance() -> None:
    payload = {
        "articles": [
            {
                "url": "https://example.com/reliance-results",
                "title": "Reliance reports quarterly results",
                "seendate": "20260105T101500Z",
                "domain": "example.com",
                "language": "English",
                "sourcecountry": "India",
            }
        ]
    }
    provider = GdeltNewsProvider(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    )
    try:
        batch = provider.fetch_content(
            symbol="RELIANCE.NS",
            query='"Reliance Industries"',
            timespan="1week",
            max_records=10,
        )
    finally:
        provider.close()

    assert len(batch.records) == 1
    assert batch.records[0].symbols == ["RELIANCE.NS"]
    assert batch.records[0].metadata["source_country"] == "India"
