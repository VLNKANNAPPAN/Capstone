from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Literal, Protocol

from market_platform.analytics.technical import TechnicalAnalyticsService
from market_platform.data.entity_linking import canonical_headline
from market_platform.db.repository import SqlAlchemyDataRepository
from market_platform.domain.models import ContentType, DisclosureType, ensure_utc, utc_now
from market_platform.fundamentals.models import FundamentalPeriod
from market_platform.research.models import (
    DataCoverage,
    EvidenceItem,
    ExplainResearchRequest,
    ResearchClaim,
    ResearchNarrative,
    ResearchNarrativePayload,
    ResearchSnapshot,
)

PROMPT_VERSION = "india-research-v1"


class NarrativeGenerator(Protocol):
    model: str

    def generate(
        self,
        *,
        snapshot: ResearchSnapshot,
        request: ExplainResearchRequest,
    ) -> ResearchNarrativePayload: ...


class ResearchSnapshotService:
    def __init__(self, repository: SqlAlchemyDataRepository) -> None:
        self._repository = repository
        self._technical = TechnicalAnalyticsService(repository)

    def build(
        self,
        *,
        symbol: str,
        cutoff: datetime | None = None,
    ) -> ResearchSnapshot | None:
        normalized_symbol = symbol.strip().upper()
        asset = self._repository.get_asset(normalized_symbol)
        if asset is None:
            return None
        point_in_time = ensure_utc(cutoff) if cutoff else datetime.now(UTC)
        technical = self._technical.snapshot(
            symbol=normalized_symbol,
            cutoff=point_in_time,
            timeframe="1Day",
        )
        if technical is None:
            return None
        all_content = self._repository.list_content_as_of(
            symbol=normalized_symbol,
            cutoff=point_in_time,
            limit=100,
        )
        news_content = [item for item in all_content if item.content_type == ContentType.NEWS][:8]
        video_content = [item for item in all_content if item.content_type == ContentType.VIDEO][:4]
        content = sorted(
            [*news_content, *video_content],
            key=lambda item: item.published_at,
            reverse=True,
        )
        all_disclosures = self._repository.list_disclosures_as_of(
            symbol=normalized_symbol,
            cutoff=point_in_time,
            limit=500,
        )
        disclosures = all_disclosures[:12]
        if not any(item.disclosure_type == DisclosureType.FINANCIAL_RESULT for item in disclosures):
            latest_result = next(
                (
                    item
                    for item in all_disclosures
                    if item.disclosure_type == DisclosureType.FINANCIAL_RESULT
                ),
                None,
            )
            if latest_result is not None:
                disclosures.append(latest_result)
        fundamental_periods = self._repository.list_fundamental_periods_as_of(
            symbol=normalized_symbol,
            cutoff=point_in_time,
            limit=8,
        )
        macro = self._repository.list_macro_as_of(
            cutoff=point_in_time,
            latest_per_series=True,
            limit=12,
        )
        evidence = _technical_evidence(technical, point_in_time)
        seen_headlines: set[str] = set()
        for item in content:
            canonical = str(
                item.metadata.get("canonical_headline") or canonical_headline(item.title)
            )
            if canonical in seen_headlines:
                continue
            seen_headlines.add(canonical)
            direction: Literal["supporting", "contradicting", "neutral", "risk"] = "neutral"
            if item.sentiment_score is not None and item.sentiment_score >= 0.2:
                direction = "supporting"
            elif item.sentiment_score is not None and item.sentiment_score <= -0.2:
                direction = "contradicting"
            is_video = item.content_type == ContentType.VIDEO
            evidence.append(
                EvidenceItem(
                    evidence_id=(
                        f"video:{item.source}:{item.external_id[:16]}"
                        if is_video
                        else f"news:{item.source}:{item.external_id[:16]}"
                    ),
                    category="video_event" if is_video else "news_event",
                    title=item.title,
                    detail=(
                        item.summary
                        or "News metadata discovered by the configured provider; "
                        "article text was not stored."
                    ),
                    direction=direction,
                    source_type="youtube_video" if is_video else "news",
                    source_id=f"{item.source}:{item.external_id}",
                    source_url=item.url,
                    observed_at=item.published_at,
                    freshness=_freshness(item.published_at, point_in_time),
                )
            )

        for disclosure in disclosures:
            is_result = disclosure.disclosure_type == DisclosureType.FINANCIAL_RESULT
            evidence.append(
                EvidenceItem(
                    evidence_id=f"disclosure:{disclosure.source}:{disclosure.external_id}",
                    category="fundamental" if is_result else "corporate_event",
                    title=disclosure.headline,
                    detail=(
                        disclosure.summary
                        or f"{disclosure.category} published through {disclosure.exchange}."
                    ),
                    direction="neutral",
                    source_type="exchange_filing",
                    source_id=f"{disclosure.source}:{disclosure.external_id}",
                    source_url=disclosure.document_url,
                    observed_at=disclosure.published_at,
                    freshness=_freshness(disclosure.published_at, point_in_time),
                )
            )

        latest_fundamental = _latest_fundamental_period(fundamental_periods)
        if latest_fundamental is not None:
            priority_metrics = {
                "revenue",
                "net_profit",
                "net_profit_parent",
                "operating_margin_pct",
                "ebitda_margin_pct",
                "basic_eps",
                "interest_coverage",
                "audit_qualification_status",
            }
            for fact in latest_fundamental.metrics:
                if fact.metric not in priority_metrics:
                    continue
                is_audit_caution = (
                    fact.metric == "audit_qualification_status"
                    and fact.text_value is not None
                    and not any(
                        token in fact.text_value.casefold()
                        for token in ("not applicable", "unmodified")
                    )
                )
                evidence.append(
                    EvidenceItem(
                        evidence_id=fact.evidence_id,
                        category="fundamental_fact",
                        title=fact.metric.replace("_", " ").title(),
                        detail=_filing_value_detail(
                            fact.metric,
                            fact.value,
                            fact.text_value,
                            fact.unit,
                            latest_fundamental.period_end,
                            latest_fundamental.basis,
                        ),
                        direction="risk" if is_audit_caution else "neutral",
                        source_type="exchange_xbrl_fact",
                        source_id=(
                            f"{latest_fundamental.document_id}:{fact.source_concept}"
                        ),
                        source_url=latest_fundamental.source_url,
                        observed_at=latest_fundamental.available_at,
                        freshness=_freshness(latest_fundamental.available_at, point_in_time),
                    )
                )

        for observation in macro:
            detail = f"{observation.title}: {observation.value} {observation.unit}."
            evidence.append(
                EvidenceItem(
                    evidence_id=(
                        f"macro:{observation.series_id}:{observation.event_time.date().isoformat()}"
                    ),
                    category="macro",
                    title=observation.title,
                    detail=detail,
                    direction="neutral",
                    source_type="rbi_series",
                    source_id=observation.series_id,
                    source_url=observation.source_url,
                    observed_at=observation.event_time,
                    freshness=_freshness(observation.event_time, point_in_time),
                )
            )

        has_fundamentals = any(
            item.disclosure_type == DisclosureType.FINANCIAL_RESULT for item in all_disclosures
        )
        has_news = any(item.content_type == ContentType.NEWS for item in all_content)
        has_video = any(item.content_type == ContentType.VIDEO for item in all_content)
        missing = ["social"]
        if not has_fundamentals:
            missing.append("fundamentals")
        if not macro:
            missing.append("macro")
        if not has_news:
            missing.append("news")
        if not has_video:
            missing.append("video")
        claims = _claims_from_evidence(technical, evidence, has_news)
        claims.extend(_context_claims(evidence, has_fundamentals, bool(macro)))
        return ResearchSnapshot(
            symbol=normalized_symbol,
            company_name=asset.name,
            exchange=asset.exchange,
            currency=asset.currency,
            generated_at=utc_now(),
            cutoff=point_in_time,
            technical=technical,
            evidence=evidence,
            claims=claims,
            coverage=DataCoverage(
                price_history=True,
                technical_metrics=True,
                news=has_news,
                fundamentals=has_fundamentals,
                macro=bool(macro),
                video=has_video,
                social=False,
                missing=missing,
            ),
            methodology=(
                "Prototype snapshot for Indian equities. Claims are deterministic translations of "
                "stored point-in-time metrics, exchange disclosures, RBI observations, and linked "
                "news and YouTube metadata. Missing evidence families are explicit and must not "
                "be inferred by the LLM."
            ),
        )


class ResearchExplanationService:
    def __init__(
        self,
        *,
        repository: SqlAlchemyDataRepository,
        generator: NarrativeGenerator,
    ) -> None:
        self._repository = repository
        self._generator = generator

    def explain(
        self,
        *,
        snapshot: ResearchSnapshot,
        request: ExplainResearchRequest,
    ) -> ResearchNarrative:
        snapshot_payload = snapshot.model_dump(mode="json")
        encoded = json.dumps(snapshot_payload, sort_keys=True, separators=(",", ":"))
        snapshot_hash = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        narrative = self._generator.generate(snapshot=snapshot, request=request)
        analysis_id = str(uuid.uuid4())
        generated_at = utc_now()
        self._repository.save_research_analysis(
            analysis_id=analysis_id,
            symbol=snapshot.symbol,
            model=self._generator.model,
            prompt_version=PROMPT_VERSION,
            snapshot_hash=snapshot_hash,
            request_payload=request.model_dump(mode="json"),
            response_payload=narrative.model_dump(mode="json"),
            created_at=generated_at,
        )
        return ResearchNarrative(
            analysis_id=analysis_id,
            symbol=snapshot.symbol,
            model=self._generator.model,
            prompt_version=PROMPT_VERSION,
            snapshot_hash=snapshot_hash,
            generated_at=generated_at,
            narrative=narrative,
        )


def _technical_evidence(technical: object, cutoff: datetime) -> list[EvidenceItem]:
    from market_platform.analytics.models import TechnicalSnapshot

    if not isinstance(technical, TechnicalSnapshot):
        raise TypeError("technical snapshot required")
    values: list[EvidenceItem] = []

    def add(
        evidence_id: str,
        category: str,
        title: str,
        detail: str,
        direction: Literal["supporting", "contradicting", "neutral", "risk"],
    ) -> None:
        values.append(
            EvidenceItem(
                evidence_id=evidence_id,
                category=category,
                title=title,
                detail=detail,
                direction=direction,
                source_type="backend_metric",
                source_id=f"{technical.source}:{technical.symbol}:{technical.as_of.isoformat()}",
                observed_at=technical.as_of,
                freshness=_freshness(technical.as_of, cutoff),
            )
        )

    return_60d = technical.returns.sixty_day_pct
    add(
        "metric:return_60d",
        "technical",
        "60-day price return",
        _metric_sentence(return_60d, "%", "60-day return"),
        "supporting" if (return_60d or 0) > 0 else "contradicting",
    )
    distance_sma = technical.trend.distance_sma_20_pct
    add(
        "metric:distance_sma20",
        "technical",
        "Price versus 20-day average",
        _metric_sentence(distance_sma, "%", "distance from SMA20"),
        "supporting" if (distance_sma or 0) > 0 else "contradicting",
    )
    rsi = technical.momentum.rsi_14
    rsi_direction: Literal["supporting", "contradicting", "neutral", "risk"] = "neutral"
    if rsi is not None and rsi >= 70:
        rsi_direction = "risk"
    elif rsi is not None and rsi <= 30:
        rsi_direction = "contradicting"
    add(
        "metric:rsi14",
        "technical",
        "RSI momentum",
        _metric_sentence(rsi, "", "RSI(14)"),
        rsi_direction,
    )
    volatility = technical.risk.annualized_volatility_30d_pct
    add(
        "metric:volatility30",
        "risk",
        "Recent annualized volatility",
        _metric_sentence(volatility, "%", "30-day annualized volatility"),
        "risk",
    )
    drawdown = technical.risk.max_drawdown_252d_pct
    add(
        "metric:max_drawdown252",
        "risk",
        "One-year maximum drawdown",
        _metric_sentence(drawdown, "%", "252-day maximum drawdown"),
        "risk",
    )
    cvar = technical.risk.cvar_95_daily_pct
    add(
        "metric:cvar95",
        "risk",
        "Expected loss in the worst daily tail",
        _metric_sentence(cvar, "%", "95% historical daily CVaR"),
        "risk",
    )
    volume_ratio = technical.liquidity.volume_ratio_20d
    add(
        "metric:volume_ratio20",
        "liquidity",
        "Volume versus recent norm",
        _metric_sentence(volume_ratio, "x", "latest volume / 20-day average"),
        "neutral",
    )
    return values


def _claims_from_evidence(
    technical: object,
    evidence: list[EvidenceItem],
    has_news: bool,
) -> list[ResearchClaim]:
    from market_platform.analytics.models import TechnicalSnapshot

    if not isinstance(technical, TechnicalSnapshot):
        raise TypeError("technical snapshot required")
    trend_support = ["metric:return_60d", "metric:distance_sma20", "metric:rsi14"]
    risk_support = ["metric:volatility30", "metric:max_drawdown252", "metric:cvar95"]
    news_ids = [item.evidence_id for item in evidence if item.source_type == "news"]
    trend_status: Literal["supported", "mixed", "caution", "insufficient_data"] = (
        "supported" if technical.signal == "positive trend" else "mixed"
    )
    if technical.signal in {"negative trend", "oversold"}:
        trend_status = "caution"
    return [
        ResearchClaim(
            claim_id="claim:technical_regime",
            claim_type="technical",
            claim=f"The current price-derived regime is {technical.signal}.",
            evidence_ids=trend_support,
            confidence=0.78 if technical.observation_count >= 200 else 0.6,
            status=trend_status,
        ),
        ResearchClaim(
            claim_id="claim:downside_risk",
            claim_type="risk",
            claim="Recent downside risk must be considered alongside momentum.",
            evidence_ids=risk_support,
            confidence=0.8 if technical.risk.cvar_95_daily_pct is not None else 0.5,
            status="caution",
        ),
        ResearchClaim(
            claim_id="claim:news_context",
            claim_type="news_event",
            claim=(
                "Recent linked news is available for contextual review."
                if has_news
                else "No linked news is available in the current snapshot."
            ),
            evidence_ids=news_ids,
            confidence=0.55 if has_news else 0.0,
            status="mixed" if has_news else "insufficient_data",
        ),
    ]


def _context_claims(
    evidence: list[EvidenceItem],
    has_fundamentals: bool,
    has_macro: bool,
) -> list[ResearchClaim]:
    fundamental_ids = [
        item.evidence_id
        for item in evidence
        if item.category in {"fundamental", "fundamental_fact"}
    ]
    macro_ids = [item.evidence_id for item in evidence if item.category == "macro"]
    return [
        ResearchClaim(
            claim_id="claim:fundamental_context",
            claim_type="fundamental",
            claim=(
                "Exchange-published financial-result context is available."
                if has_fundamentals
                else "No exchange-published financial-result context is stored."
            ),
            evidence_ids=fundamental_ids,
            confidence=0.9 if has_fundamentals else 0.0,
            status="supported" if has_fundamentals else "insufficient_data",
        ),
        ResearchClaim(
            claim_id="claim:macro_context",
            claim_type="macro",
            claim=(
                "RBI macro and interest-rate observations are available for context."
                if has_macro
                else "No RBI macro observations are stored."
            ),
            evidence_ids=macro_ids,
            confidence=0.88 if has_macro else 0.0,
            status="supported" if has_macro else "insufficient_data",
        ),
    ]


def _metric_sentence(value: float | None, suffix: str, label: str) -> str:
    if value is None:
        return f"{label} is unavailable because the stored history is insufficient."
    return f"{label}: {value:.2f}{suffix}."


def _latest_fundamental_period(
    periods: list[FundamentalPeriod],
) -> FundamentalPeriod | None:
    if not periods:
        return None
    latest_end = max(period.period_end or "" for period in periods)
    latest = [period for period in periods if (period.period_end or "") == latest_end]
    return next((period for period in latest if period.basis == "consolidated"), latest[0])


def _filing_value_detail(
    metric: str,
    value: float | None,
    text_value: str | None,
    unit: str | None,
    period_end: str | None,
    basis: str,
) -> str:
    suffix = f" for the {basis} period ending {period_end or 'unknown'}"
    if text_value is not None:
        return f"{text_value[:500]}{suffix}."
    if value is None:
        return f"Value unavailable{suffix}."
    if unit == "INR":
        return f"{metric.replace('_', ' ')}: ₹{value / 10_000_000:,.2f} crore{suffix}."
    if unit == "percent":
        return f"{metric.replace('_', ' ')}: {value:.2f}%{suffix}."
    if unit == "ratio":
        return f"{metric.replace('_', ' ')}: {value:.2f}x{suffix}."
    return f"{metric.replace('_', ' ')}: {value:,.2f} {unit or ''}{suffix}."


def _freshness(
    observed_at: datetime,
    cutoff: datetime,
) -> Literal["fresh", "recent", "aging", "stale"]:
    days = max(0, (cutoff - observed_at).days)
    if days <= 2:
        return "fresh"
    if days <= 14:
        return "recent"
    if days <= 90:
        return "aging"
    return "stale"
