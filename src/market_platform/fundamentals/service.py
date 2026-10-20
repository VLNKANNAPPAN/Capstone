from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from market_platform.domain.models import (
    CorporateDisclosure,
    DisclosureType,
    ensure_utc,
    utc_now,
)
from market_platform.fundamentals.models import (
    FilingRefreshResult,
    FundamentalInsight,
    FundamentalPeriod,
    FundamentalSnapshot,
)
from market_platform.fundamentals.xbrl import XbrlDocumentClient, parse_xbrl

if TYPE_CHECKING:
    from market_platform.db.repository import SqlAlchemyDataRepository


class FilingIntelligenceService:
    def __init__(
        self,
        repository: SqlAlchemyDataRepository,
        *,
        client: XbrlDocumentClient | None = None,
    ) -> None:
        self._repository = repository
        self._client = client

    def refresh(self, *, symbol: str, limit: int = 8) -> FilingRefreshResult:
        normalized_symbol = symbol.strip().upper()
        disclosures = self._repository.list_disclosures_as_of(
            symbol=normalized_symbol,
            cutoff=datetime.now(UTC),
            limit=500,
        )
        candidates = [
            item
            for item in disclosures
            if item.disclosure_type == DisclosureType.FINANCIAL_RESULT
            and item.document_url
            and item.document_url.casefold().endswith((".xml", ".xhtml", ".html"))
        ]
        selected = _select_filings(candidates, limit)
        result = FilingRefreshResult(symbol=normalized_symbol, considered_filings=len(selected))
        client = self._client or XbrlDocumentClient()
        owns_client = self._client is None
        try:
            for disclosure in selected:
                assert disclosure.document_url is not None
                try:
                    content, checksum, content_type = client.download(disclosure.document_url)
                    existing = self._repository.find_filing_document_revision(
                        source=disclosure.source,
                        filing_external_id=disclosure.external_id,
                        checksum=checksum,
                    )
                    if existing is not None:
                        result.cached_documents += 1
                        continue
                    parsed = parse_xbrl(content, expected_period_end=disclosure.period_end)
                    document_id = str(
                        uuid.uuid5(
                            uuid.NAMESPACE_URL,
                            f"{disclosure.source}:{disclosure.external_id}:{checksum}",
                        )
                    )
                    fact_count = self._repository.save_filing_extraction(
                        document_id=document_id,
                        source=disclosure.source,
                        filing_external_id=disclosure.external_id,
                        symbol=normalized_symbol,
                        source_url=disclosure.document_url,
                        content_type=content_type,
                        checksum=checksum,
                        content_text=content,
                        parsed=parsed,
                        available_at=disclosure.available_at,
                        retrieved_at=utc_now(),
                    )
                    result.downloaded_documents += 1
                    result.parsed_documents += 1
                    result.normalized_facts += fact_count
                except (RuntimeError, ValueError) as exc:
                    result.failed_documents += 1
                    result.warnings.append(
                        f"{disclosure.external_id}: {str(exc)[:180]}"
                    )
        finally:
            if owns_client:
                client.close()
        return result

    def snapshot(
        self,
        *,
        symbol: str,
        cutoff: datetime | None = None,
        limit: int = 12,
    ) -> FundamentalSnapshot:
        point_in_time = ensure_utc(cutoff) if cutoff else datetime.now(UTC)
        normalized_symbol = symbol.strip().upper()
        periods = self._repository.list_fundamental_periods_as_of(
            symbol=normalized_symbol,
            cutoff=point_in_time,
            limit=limit,
        )
        latest = _preferred_latest(periods)
        coverage = _coverage(latest)
        return FundamentalSnapshot(
            symbol=normalized_symbol,
            generated_at=utc_now(),
            cutoff=point_in_time,
            period_count=len(periods),
            latest_period_end=latest.period_end if latest else None,
            latest_basis=latest.basis if latest else None,
            periods=periods,
            insights=_insights(periods, latest),
            coverage=coverage,
            methodology=(
                "Facts are parsed deterministically from official NSE/BSE XBRL or iXBRL "
                "documents and retain filing URL, concept, period, basis, audit status and "
                "available_at provenance. Derived margins use declared formulas. Missing concepts "
                "remain unavailable; no value is estimated by an LLM."
            ),
        )


def _select_filings(
    disclosures: list[CorporateDisclosure], limit: int
) -> list[CorporateDisclosure]:
    selected: list[CorporateDisclosure] = []
    seen: set[tuple[str | None, str]] = set()
    ordered = sorted(
        disclosures,
        key=lambda item: (
            _period_sort_key(item.period_end),
            "consolidated" in str(item.metadata.get("consolidated", "")).casefold(),
            item.available_at,
        ),
        reverse=True,
    )
    for item in ordered:
        basis = str(item.metadata.get("consolidated") or "unknown").casefold()
        key = (item.period_end, basis)
        if key in seen:
            continue
        seen.add(key)
        selected.append(item)
        if len(selected) >= limit:
            break
    return selected


def _period_sort_key(value: str | None) -> int:
    if not value:
        return -1
    for date_format in ("%Y-%m-%d", "%d-%b-%Y"):
        try:
            return datetime.strptime(value.strip(), date_format).date().toordinal()
        except ValueError:
            continue
    return -1


def _preferred_latest(periods: list[FundamentalPeriod]) -> FundamentalPeriod | None:
    if not periods:
        return None
    latest_end = max(period.period_end or "" for period in periods)
    latest = [period for period in periods if (period.period_end or "") == latest_end]
    return next((period for period in latest if period.basis == "consolidated"), latest[0])


def _metric_map(period: FundamentalPeriod | None) -> dict[str, float]:
    if period is None:
        return {}
    return {
        metric.metric: metric.value
        for metric in period.metrics
        if metric.value is not None
    }


def _coverage(period: FundamentalPeriod | None) -> dict[str, bool]:
    metrics = _metric_map(period)
    return {
        "revenue": "revenue" in metrics or "total_income" in metrics,
        "profit": "net_profit" in metrics or "net_profit_parent" in metrics,
        "eps": "basic_eps" in metrics,
        "margins": "net_margin_pct" in metrics,
        "interest_coverage": "interest_coverage" in metrics,
        "cash_flow": False,
        "balance_sheet": False,
    }


def _insights(
    periods: list[FundamentalPeriod], latest: FundamentalPeriod | None
) -> list[FundamentalInsight]:
    if latest is None:
        return []
    metrics = _metric_map(latest)
    facts = {fact.metric: fact for fact in latest.metrics}
    insights: list[FundamentalInsight] = []
    net_margin = metrics.get("net_margin_pct")
    if net_margin is not None:
        insights.append(
            FundamentalInsight(
                insight_id="fundamental:net_margin",
                kind="profitability",
                severity=(
                    "positive"
                    if net_margin >= 10
                    else "caution" if net_margin < 3 else "neutral"
                ),
                title="Latest net margin",
                detail=(
                    f"Net profit is {net_margin:.2f}% of reported revenue for the latest period."
                ),
                evidence_ids=[facts["net_margin_pct"].evidence_id],
            )
        )
    interest_coverage = metrics.get("interest_coverage")
    if interest_coverage is not None:
        insights.append(
            FundamentalInsight(
                insight_id="fundamental:interest_coverage",
                kind="risk",
                severity=(
                    "positive"
                    if interest_coverage >= 5
                    else "caution" if interest_coverage < 2 else "neutral"
                ),
                title="Interest coverage",
                detail=(
                    f"Estimated EBIT covers reported finance costs {interest_coverage:.2f} times."
                ),
                evidence_ids=[facts["interest_coverage"].evidence_id],
            )
        )
    comparable = [
        period
        for period in periods
        if period.document_id != latest.document_id and period.basis == latest.basis
    ]
    previous = comparable[0] if comparable else None
    previous_metrics = _metric_map(previous)
    current_revenue = metrics.get("revenue") or metrics.get("total_income")
    previous_revenue = previous_metrics.get("revenue") or previous_metrics.get("total_income")
    if (
        current_revenue is not None
        and previous_revenue is not None
        and previous_revenue != 0
        and previous is not None
    ):
        growth = (current_revenue / previous_revenue - 1) * 100
        current_fact = facts.get("revenue") or facts.get("total_income")
        prior_facts = {fact.metric: fact for fact in previous.metrics}
        prior_fact = prior_facts.get("revenue") or prior_facts.get("total_income")
        evidence_ids = [fact.evidence_id for fact in (current_fact, prior_fact) if fact]
        insights.append(
            FundamentalInsight(
                insight_id="fundamental:sequential_revenue_growth",
                kind="growth",
                severity="positive" if growth > 0 else "caution",
                title="Sequential reported revenue change",
                detail=(
                    f"Revenue changed {growth:+.2f}% versus the previous stored {latest.basis} "
                    f"filing period ending {previous.period_end}."
                ),
                evidence_ids=evidence_ids,
            )
        )
    audit = next(
        (fact for fact in latest.metrics if fact.metric == "audit_qualification_status"),
        None,
    )
    if audit and audit.text_value:
        normalized = audit.text_value.casefold()
        caution = not any(value in normalized for value in ("not applicable", "unmodified"))
        insights.append(
            FundamentalInsight(
                insight_id="fundamental:audit_status",
                kind="quality",
                severity="caution" if caution else "neutral",
                title="Audit qualification status",
                detail=audit.text_value[:300],
                evidence_ids=[audit.evidence_id],
            )
        )
    insights.append(
        FundamentalInsight(
            insight_id="fundamental:cashflow_gap",
            kind="data_quality",
            severity="neutral",
            title="Cash-flow quality not yet scored",
            detail=(
                "This filing does not provide enough normalized cash-flow and balance-sheet facts "
                "for FCF, ROE or debt-quality conclusions."
            ),
            evidence_ids=[],
        )
    )
    return insights
