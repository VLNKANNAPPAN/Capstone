from __future__ import annotations

from datetime import UTC, datetime

from market_platform.data.normalization import normalize_alpaca_bar, normalize_sec_filing


def test_price_bar_becomes_available_after_interval() -> None:
    payload = {
        "t": "2026-01-05T14:30:00Z",
        "o": 100,
        "h": 102,
        "l": 99,
        "c": 101,
        "v": 500,
    }
    raw, bar, issue = normalize_alpaca_bar(symbol="aapl", timeframe="1Min", payload=payload)

    assert issue is None
    assert raw is not None
    assert bar is not None
    assert bar.symbol == "AAPL"
    assert bar.available_at == datetime(2026, 1, 5, 14, 31, tzinfo=UTC)


def test_invalid_ohlc_is_quarantined() -> None:
    payload = {
        "t": "2026-01-05T14:30:00Z",
        "o": 100,
        "h": 98,
        "l": 99,
        "c": 101,
        "v": 500,
    }
    raw, bar, issue = normalize_alpaca_bar(symbol="AAPL", timeframe="1Min", payload=payload)

    assert raw is None
    assert bar is None
    assert issue is not None
    assert issue.code == "invalid_price_bar"


def test_sec_acceptance_time_controls_availability() -> None:
    payload = {
        "accessionNumber": "0000320193-26-000001",
        "filingDate": "2026-01-30",
        "reportDate": "2025-12-27",
        "acceptanceDateTime": "2026-01-30T16:10:00Z",
        "form": "10-Q",
        "primaryDocument": "aapl-20251227.htm",
    }
    raw, document, issue = normalize_sec_filing(symbol="AAPL", cik="320193", payload=payload)

    assert issue is None
    assert raw is not None
    assert document is not None
    assert document.available_at == datetime(2026, 1, 30, 16, 10, tzinfo=UTC)
    assert document.report_date == "2025-12-27"
