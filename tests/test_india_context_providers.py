from __future__ import annotations

import json
from datetime import date

import httpx

from market_platform.data.entity_linking import IndiaEquityEntityLinker
from market_platform.data.providers.corporate import BseCorporateProvider, NseCorporateProvider
from market_platform.data.providers.google_news import GoogleNewsRssProvider
from market_platform.data.providers.rbi import RbiMacroProvider
from market_platform.domain.models import DisclosureType
from market_platform.research_universe import INDIA_RESEARCH_UNIVERSE


def test_google_news_requires_an_entity_match_and_deduplicates() -> None:
    rss = """<?xml version="1.0"?><rss><channel>
      <item><title>Reliance Industries raises debt - Business Standard</title>
        <link>https://news.google.com/a</link><guid>a</guid>
        <pubDate>Thu, 24 Sep 2026 07:45:45 GMT</pubDate>
        <source url="https://www.business-standard.com">Business Standard</source></item>
      <item><title>Unrelated market story - Publisher</title>
        <link>https://news.google.com/b</link><guid>b</guid>
        <pubDate>Thu, 24 Sep 2026 08:45:45 GMT</pubDate>
        <source url="https://example.com">Publisher</source></item>
    </channel></rss>"""

    provider = GoogleNewsRssProvider(
        entity_linker=IndiaEquityEntityLinker(INDIA_RESEARCH_UNIVERSE),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text=rss)),
    )
    try:
        batch = provider.fetch_content(
            symbol="RELIANCE.NS",
            query='"Reliance Industries"',
            max_records=10,
        )
    finally:
        provider.close()

    assert len(batch.records) == 1
    assert batch.records[0].symbols == ["RELIANCE.NS"]
    assert batch.records[0].metadata["entity_link_confidence"] == 0.98
    assert batch.issues[0].code == "entity_not_confirmed"


def test_nse_corporate_provider_normalizes_announcements_and_results() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/companies-listing/"):
            return httpx.Response(200, text="ok")
        if request.url.path == "/api/corporate-announcements":
            return httpx.Response(
                200,
                json=[
                    {
                        "seq_id": "a1",
                        "an_dt": "25-Sep-2026 22:49:03",
                        "exchdisstime": "25-Sep-2026 22:49:04",
                        "desc": "Credit Rating",
                        "attchmntText": "Reliance Industries credit rating update",
                        "attchmntFile": "https://nsearchives.nseindia.com/a.pdf",
                        "symbol": "RELIANCE",
                    }
                ],
            )
        return httpx.Response(
            200,
            json=[
                {
                    "seqNumber": "r1",
                    "filingDate": "16-Jan-2025 20:20",
                    "exchdisstime": "16-Jan-2025 20:20:54",
                    "relatingTo": "Third Quarter",
                    "consolidated": "Consolidated",
                    "toDate": "31-Dec-2024",
                    "xbrl": "https://nsearchives.nseindia.com/result.xml",
                }
            ],
        )

    provider = NseCorporateProvider(transport=httpx.MockTransport(handler))
    try:
        batch = provider.fetch_disclosures(
            symbol="RELIANCE.NS",
            start=date(2026, 9, 20),
            end=date(2026, 9, 26),
        )
    finally:
        provider.close()

    assert {item.disclosure_type for item in batch.records} == {
        DisclosureType.ANNOUNCEMENT,
        DisclosureType.FINANCIAL_RESULT,
    }
    assert all(item.symbol == "RELIANCE.NS" for item in batch.records)


def test_bse_provider_adds_result_snapshot_with_first_observed_availability() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("AnnSubCategoryGetData/w"):
            return httpx.Response(
                200,
                json={
                    "Table": [
                        {
                            "NEWSID": "b1",
                            "NEWS_DT": "2026-09-25T22:13:19.383",
                            "DissemDT": "2026-09-25T22:13:19.383",
                            "NEWSSUB": "Credit rating update",
                            "SUBCATNAME": "Credit Rating",
                            "MORE": "Rating assigned",
                            "ATTACHMENTNAME": "result.pdf",
                            "SLONGNAME": "Reliance Industries Ltd",
                        }
                    ]
                },
            )
        inner = {
            "resultinCr": [
                {"title": "Revenue", "v1": "1,000", "v2": "900", "v3": "3,500"},
                {"title": "Net Profit", "v1": "100", "v2": "90", "v3": "340"},
                {"title": "EPS", "v1": "9", "v2": "8", "v3": "30"},
            ],
            "resultinS": [
                {"LQ": "Jun-26", "SQ": "Mar-26", "FY": "FY25-26", "LLQ": "https://bse/1"}
            ],
        }
        return httpx.Response(200, json=json.dumps(inner))

    provider = BseCorporateProvider(
        bse_codes={"RELIANCE.NS": "500325"},
        transport=httpx.MockTransport(handler),
    )
    try:
        batch = provider.fetch_disclosures(
            symbol="RELIANCE.NS",
            start=date(2026, 9, 20),
            end=date(2026, 9, 26),
        )
    finally:
        provider.close()

    results = [
        item for item in batch.records if item.disclosure_type is DisclosureType.FINANCIAL_RESULT
    ]
    assert len(results) == 3
    assert results[0].available_at > results[0].published_at
    assert results[0].metadata["point_in_time_note"]


def test_rbi_provider_normalizes_three_series_and_current_policy_rates() -> None:
    def data_handler(request: httpx.Request) -> httpx.Response:
        if "cpi_av_rn" in request.url.path:
            columns = ["time_period", "obs_value"]
            row = ["2025-12-31", 1.3]
        elif "qtr_gdp" in request.url.path:
            columns = ["time_period", "obs_value"]
            row = ["2025-09-30", 48633401663035.8]
        else:
            columns = ["time_period", "obs_value"]
            row = ["2026-09-11", "5.020737"]
        return httpx.Response(200, json={"columns": columns, "rows": [row]})

    rates = " ".join(
        [
            "Policy Repo Rate : 5.25%",
            "Standing Deposit Facility Rate : 5.00%",
            "Marginal Standing Facility Rate : 5.50%",
            "Bank Rate : 5.50%",
            "Fixed Reverse Repo Rate : 3.35%",
            "CRR : 3.00%",
            "SLR : 18.00%",
        ]
    )
    provider = RbiMacroProvider(
        data_transport=httpx.MockTransport(data_handler),
        current_transport=httpx.MockTransport(lambda request: httpx.Response(200, text=rates)),
    )
    try:
        batch = provider.fetch_observations(history_limit=1)
    finally:
        provider.close()

    assert len(batch.records) == 10
    assert not batch.issues
    assert {item.series_id for item in batch.records} >= {
        "rbi.cpi_combined_yoy",
        "rbi.real_gdp_quarterly",
        "rbi.weighted_average_call_rate",
        "rbi.policy_repo_rate",
    }
