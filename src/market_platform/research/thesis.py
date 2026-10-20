from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Literal

from market_platform.db.repository import SqlAlchemyDataRepository
from market_platform.domain.models import ensure_utc, utc_now
from market_platform.research.models import (
    EvidenceContradiction,
    EvidenceSensitivity,
    ResearchSnapshot,
    ThesisBreaker,
    ThesisChange,
    ThesisEvaluation,
    ThesisMetricState,
    ThesisOutcomePoint,
    ThesisVersion,
)
from market_platform.research.service import ResearchSnapshotService

THESIS_METHODOLOGY_VERSION = "thesis-v2"


class ThesisVersionService:
    """Persist and compare deterministic point-in-time research states."""

    def __init__(self, repository: SqlAlchemyDataRepository) -> None:
        self._repository = repository
        self._snapshots = ResearchSnapshotService(repository)

    def create(self, *, symbol: str, cutoff: datetime | None = None) -> ThesisVersion | None:
        point_in_time = ensure_utc(cutoff) if cutoff else datetime.now(UTC)
        snapshot = self._snapshots.build(symbol=symbol, cutoff=point_in_time)
        if snapshot is None:
            return None
        snapshot_hash = _snapshot_hash(snapshot)
        existing = self._repository.find_thesis_version_by_hash(
            symbol=snapshot.symbol, snapshot_hash=snapshot_hash
        )
        if existing is not None:
            return ThesisVersion.model_validate(existing)

        previous_payload = self._repository.latest_thesis_before(
            symbol=snapshot.symbol, cutoff=point_in_time
        )
        previous = (
            ThesisVersion.model_validate(previous_payload) if previous_payload is not None else None
        )
        metrics = _metric_state(snapshot)
        breakers = evaluate_breakers(metrics)
        coverage = _coverage_score(snapshot)
        state = _state(metrics, breakers)
        confidence = _confidence(snapshot, breakers, coverage)
        contradictions = detect_contradictions(snapshot, metrics)
        sensitivity = analyze_evidence_sensitivity(
            snapshot, breakers, coverage, confidence
        )
        existing_versions = self._repository.list_thesis_versions(
            symbol=snapshot.symbol, limit=5000
        )
        created_at = utc_now()
        thesis = ThesisVersion(
            thesis_id=str(uuid.uuid4()),
            symbol=snapshot.symbol,
            version_number=len(existing_versions) + 1,
            cutoff=point_in_time,
            as_of=snapshot.technical.as_of,
            created_at=created_at,
            previous_version_id=previous.thesis_id if previous else None,
            snapshot_hash=snapshot_hash,
            state=state,
            confidence=confidence,
            evidence_coverage_pct=coverage,
            metrics=metrics,
            breakers=breakers,
            changes=compare_theses(previous, metrics, breakers, state, coverage),
            contradictions=contradictions,
            sensitivity=sensitivity,
            methodology_version=THESIS_METHODOLOGY_VERSION,
            methodology=(
                "Immutable point-in-time replay using only records whose available_at is at or "
                "before the cutoff. Changes use fixed, declared materiality thresholds; breaker "
                "rules are deterministic and do not use an LLM. Confidence measures evidence "
                "coverage and history sufficiency, not probability of a future return. "
                "Contradictions and leave-one-category-out sensitivity are diagnostic, not causal."
            ),
        )
        payload = thesis.model_dump(mode="json")
        self._repository.save_thesis_version(
            thesis_id=thesis.thesis_id,
            symbol=thesis.symbol,
            cutoff=thesis.cutoff,
            as_of=thesis.as_of,
            previous_version_id=thesis.previous_version_id,
            snapshot_hash=thesis.snapshot_hash,
            state=thesis.state,
            confidence=thesis.confidence,
            payload=payload,
            created_at=thesis.created_at,
        )
        return thesis

    def list(self, *, symbol: str, limit: int = 24) -> list[ThesisVersion]:
        return [
            ThesisVersion.model_validate(payload)
            for payload in self._repository.list_thesis_versions(symbol=symbol, limit=limit)
        ]


def _snapshot_hash(snapshot: ResearchSnapshot) -> str:
    stable = {
        "methodology_version": THESIS_METHODOLOGY_VERSION,
        "snapshot": snapshot.model_dump(mode="json", exclude={"generated_at"}),
    }
    encoded = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _metric_state(snapshot: ResearchSnapshot) -> ThesisMetricState:
    technical = snapshot.technical
    return ThesisMetricState(
        close=technical.close,
        signal=technical.signal,
        return_60d_pct=technical.returns.sixty_day_pct,
        distance_sma_20_pct=technical.trend.distance_sma_20_pct,
        rsi_14=technical.momentum.rsi_14,
        volatility_30d_pct=technical.risk.annualized_volatility_30d_pct,
        maximum_drawdown_252d_pct=technical.risk.max_drawdown_252d_pct,
        sharpe_252d=technical.risk.sharpe_252d,
        cvar_95_daily_pct=technical.risk.cvar_95_daily_pct,
    )


def evaluate_breakers(metrics: ThesisMetricState) -> list[ThesisBreaker]:
    rules: list[
        tuple[
            str,
            str,
            str,
            Literal["lt", "lte", "gt", "gte"],
            float,
            float | None,
            Literal["monitor", "material", "critical"],
            str,
        ]
    ] = [
        (
            "breaker:trend_below_sma20",
            "Price loses its 20-day trend",
            "distance_sma_20_pct",
            "lt",
            0.0,
            metrics.distance_sma_20_pct,
            "material",
            "A close below SMA20 weakens the current trend thesis.",
        ),
        (
            "breaker:momentum_60d_negative",
            "Sixty-day momentum turns negative",
            "return_60d_pct",
            "lt",
            0.0,
            metrics.return_60d_pct,
            "material",
            "Negative medium-term momentum contradicts a constructive price thesis.",
        ),
        (
            "breaker:drawdown_20",
            "Drawdown exceeds 20%",
            "maximum_drawdown_252d_pct",
            "lte",
            -20.0,
            metrics.maximum_drawdown_252d_pct,
            "critical",
            "A 20% peak-to-trough loss indicates material capital impairment risk.",
        ),
        (
            "breaker:tail_loss_3",
            "Worst-tail daily loss exceeds 3%",
            "cvar_95_daily_pct",
            "lte",
            -3.0,
            metrics.cvar_95_daily_pct,
            "critical",
            "Large average losses in the worst 5% of days indicate elevated tail risk.",
        ),
        (
            "breaker:negative_sharpe",
            "Risk-adjusted return is negative",
            "sharpe_252d",
            "lt",
            0.0,
            metrics.sharpe_252d,
            "monitor",
            "A negative Sharpe ratio means recent excess return did not compensate for volatility.",
        ),
        (
            "breaker:rsi_overheated",
            "Momentum is overheated",
            "rsi_14",
            "gte",
            75.0,
            metrics.rsi_14,
            "monitor",
            "RSI at or above 75 can signal extension and a higher pullback risk.",
        ),
    ]
    result: list[ThesisBreaker] = []
    for rule_id, label, metric, operator, threshold, value, severity, interpretation in rules:
        breached = value is not None and _compare(value, operator, threshold)
        result.append(
            ThesisBreaker(
                rule_id=rule_id,
                label=label,
                metric=metric,
                operator=operator,
                threshold=threshold,
                current_value=value,
                breached=breached,
                severity=severity,
                interpretation=interpretation,
            )
        )
    return result


def _compare(value: float, operator: str, threshold: float) -> bool:
    if operator == "lt":
        return value < threshold
    if operator == "lte":
        return value <= threshold
    if operator == "gt":
        return value > threshold
    return value >= threshold


def compare_theses(
    previous: ThesisVersion | None,
    current: ThesisMetricState,
    breakers: list[ThesisBreaker],
    state: str,
    coverage: float,
) -> list[ThesisChange]:
    if previous is None:
        return [
            ThesisChange(
                field="baseline",
                label="Replay baseline created",
                previous_value=None,
                current_value=state,
                material=True,
                interpretation="This is the first persisted point-in-time thesis for the symbol.",
            )
        ]
    changes: list[ThesisChange] = []
    _append_text_change(changes, "state", "Thesis state", previous.state, state)
    _append_text_change(
        changes, "signal", "Technical regime", previous.metrics.signal, current.signal
    )
    thresholds = {
        "close": ("Closing price", 5.0, True),
        "return_60d_pct": ("60-day return", 5.0, False),
        "volatility_30d_pct": ("30-day volatility", 5.0, False),
        "maximum_drawdown_252d_pct": ("Maximum drawdown", 5.0, False),
        "sharpe_252d": ("Sharpe ratio", 0.5, False),
        "cvar_95_daily_pct": ("Daily CVaR", 1.0, False),
    }
    for field, (label, threshold, relative) in thresholds.items():
        before = getattr(previous.metrics, field)
        after = getattr(current, field)
        if before is None or after is None:
            if before != after:
                changes.append(
                    ThesisChange(
                        field=field,
                        label=label,
                        previous_value=before,
                        current_value=after,
                        material=False,
                        interpretation="Metric availability changed.",
                    )
                )
            continue
        delta = after - before
        measured_delta = abs(delta / before * 100) if relative and before else abs(delta)
        material = measured_delta >= threshold
        if material:
            unit = "%" if relative else " points"
            changes.append(
                ThesisChange(
                    field=field,
                    label=label,
                    previous_value=round(before, 4),
                    current_value=round(after, 4),
                    delta=round(delta, 4),
                    material=True,
                    interpretation=f"Changed beyond the declared {threshold:g}{unit} threshold.",
                )
            )
    prior_breakers = {item.rule_id: item.breached for item in previous.breakers}
    for breaker in breakers:
        if prior_breakers.get(breaker.rule_id, False) != breaker.breached:
            changes.append(
                ThesisChange(
                    field=breaker.rule_id,
                    label=breaker.label,
                    previous_value=prior_breakers.get(breaker.rule_id, False),
                    current_value=breaker.breached,
                    material=True,
                    interpretation=(
                        "Breaker is newly breached."
                        if breaker.breached
                        else "Breaker has recovered below its trigger."
                    ),
                )
            )
    if abs(coverage - previous.evidence_coverage_pct) >= 10:
        changes.append(
            ThesisChange(
                field="evidence_coverage_pct",
                label="Evidence coverage",
                previous_value=previous.evidence_coverage_pct,
                current_value=coverage,
                delta=round(coverage - previous.evidence_coverage_pct, 2),
                material=True,
                interpretation=(
                    "Available evidence coverage changed by at least 10 percentage points."
                ),
            )
        )
    return changes


def _append_text_change(
    changes: list[ThesisChange], field: str, label: str, before: str, after: str
) -> None:
    if before != after:
        changes.append(
            ThesisChange(
                field=field,
                label=label,
                previous_value=before,
                current_value=after,
                material=True,
                interpretation=f"Changed from {before} to {after}.",
            )
        )


def _coverage_score(snapshot: ResearchSnapshot) -> float:
    coverage = snapshot.coverage
    weights = {
        "price_history": 25.0,
        "technical_metrics": 25.0,
        "news": 15.0,
        "fundamentals": 20.0,
        "macro": 10.0,
        "video": 5.0,
    }
    return round(sum(weight for field, weight in weights.items() if getattr(coverage, field)), 2)


def _confidence(
    snapshot: ResearchSnapshot, breakers: list[ThesisBreaker], coverage: float
) -> float:
    history_score = min(snapshot.technical.observation_count / 252, 1.0)
    fresh_evidence = sum(item.freshness in {"fresh", "recent"} for item in snapshot.evidence)
    return _confidence_score(
        history_score=history_score,
        fresh_evidence=fresh_evidence,
        breakers=breakers,
        coverage=coverage,
    )


def _confidence_score(
    *,
    history_score: float,
    fresh_evidence: int,
    breakers: list[ThesisBreaker],
    coverage: float,
) -> float:
    freshness_score = min(fresh_evidence / 6, 1.0)
    penalty = 0.08 * sum(item.breached and item.severity == "critical" for item in breakers)
    score = 0.25 + coverage / 200 + history_score * 0.15 + freshness_score * 0.1 - penalty
    return round(max(0.2, min(score, 0.92)), 3)


def _state(
    metrics: ThesisMetricState, breakers: list[ThesisBreaker]
) -> Literal["constructive", "neutral", "cautious", "at_risk"]:
    if any(item.breached and item.severity == "critical" for item in breakers):
        return "at_risk"
    material_count = sum(item.breached and item.severity == "material" for item in breakers)
    if material_count >= 2 or metrics.signal in {"negative trend", "oversold"}:
        return "cautious"
    if metrics.signal == "positive trend" and material_count == 0:
        return "constructive"
    return "neutral"


def detect_contradictions(
    snapshot: ResearchSnapshot, metrics: ThesisMetricState
) -> list[EvidenceContradiction]:
    """Find explicit cross-signal conflicts without asking an LLM to infer them."""
    contradictions: list[EvidenceContradiction] = []
    return_60d = metrics.return_60d_pct
    distance_sma = metrics.distance_sma_20_pct
    if (
        return_60d is not None
        and distance_sma is not None
        and return_60d * distance_sma < 0
    ):
        contradictions.append(
            EvidenceContradiction(
                contradiction_id="contradiction:trend_horizon",
                contradiction_type="technical_horizon_conflict",
                severity="medium",
                summary="Short and medium-term trend signals disagree.",
                supporting_evidence_ids=["metric:return_60d"],
                contradicting_evidence_ids=["metric:distance_sma20"],
                interpretation=(
                    "The 60-day return and distance from the 20-day average have opposite signs; "
                    "the apparent regime depends on the chosen horizon."
                ),
            )
        )

    news_supporting = [
        item.evidence_id
        for item in snapshot.evidence
        if item.category == "news_event" and item.direction == "supporting"
    ]
    news_contradicting = [
        item.evidence_id
        for item in snapshot.evidence
        if item.category == "news_event" and item.direction == "contradicting"
    ]
    if metrics.signal == "positive trend" and news_contradicting:
        contradictions.append(
            EvidenceContradiction(
                contradiction_id="contradiction:positive_price_negative_news",
                contradiction_type="price_news_divergence",
                severity="medium",
                summary="Positive price trend conflicts with negative linked news.",
                supporting_evidence_ids=["metric:return_60d", "metric:distance_sma20"],
                contradicting_evidence_ids=news_contradicting,
                interpretation=(
                    "Market behaviour remains constructive while recent linked headlines carry "
                    "negative metadata sentiment. The divergence requires monitoring."
                ),
            )
        )
    if metrics.signal in {"negative trend", "oversold"} and news_supporting:
        contradictions.append(
            EvidenceContradiction(
                contradiction_id="contradiction:negative_price_positive_news",
                contradiction_type="price_news_divergence",
                severity="medium",
                summary="Weak price action conflicts with positive linked news.",
                supporting_evidence_ids=news_supporting,
                contradicting_evidence_ids=["metric:return_60d", "metric:distance_sma20"],
                interpretation=(
                    "Positive headline sentiment has not yet been confirmed by the stored price "
                    "trend; this is a measurable narrative-versus-market disagreement."
                ),
            )
        )

    elevated_tail = (
        metrics.cvar_95_daily_pct is not None and metrics.cvar_95_daily_pct <= -2.5
    )
    deep_drawdown = (
        metrics.maximum_drawdown_252d_pct is not None
        and metrics.maximum_drawdown_252d_pct <= -15
    )
    if return_60d is not None and return_60d > 0 and (elevated_tail or deep_drawdown):
        risk_ids = [
            evidence_id
            for condition, evidence_id in (
                (elevated_tail, "metric:cvar95"),
                (deep_drawdown, "metric:max_drawdown252"),
            )
            if condition
        ]
        contradictions.append(
            EvidenceContradiction(
                contradiction_id="contradiction:return_risk",
                contradiction_type="return_risk_conflict",
                severity="high" if elevated_tail and deep_drawdown else "medium",
                summary="Positive return coexists with elevated downside risk.",
                supporting_evidence_ids=["metric:return_60d"],
                contradicting_evidence_ids=risk_ids,
                interpretation=(
                    "Momentum alone overstates thesis strength because tail loss or drawdown "
                    "remains elevated."
                ),
            )
        )
    return contradictions


def analyze_evidence_sensitivity(
    snapshot: ResearchSnapshot,
    breakers: list[ThesisBreaker],
    coverage: float,
    baseline_confidence: float,
) -> list[EvidenceSensitivity]:
    """Remove one evidence category at a time and measure confidence dependence."""
    category_rules = {
        "market_metrics": ({"technical", "risk", "liquidity"}, 25.0),
        "news": ({"news_event"}, 15.0),
        "fundamentals": ({"fundamental", "fundamental_fact", "corporate_event"}, 20.0),
        "macro": ({"macro"}, 10.0),
        "video": ({"video_event"}, 5.0),
    }
    history_score = min(snapshot.technical.observation_count / 252, 1.0)
    fresh_total = sum(item.freshness in {"fresh", "recent"} for item in snapshot.evidence)
    sensitivity: list[EvidenceSensitivity] = []
    for category, (evidence_categories, weight) in category_rules.items():
        removed = [
            item for item in snapshot.evidence if item.category in evidence_categories
        ]
        if not removed:
            continue
        removed_fresh = sum(item.freshness in {"fresh", "recent"} for item in removed)
        perturbed = _confidence_score(
            history_score=history_score,
            fresh_evidence=max(0, fresh_total - removed_fresh),
            breakers=breakers,
            coverage=max(0, coverage - weight),
        )
        delta = round(max(0.0, baseline_confidence - perturbed), 3)
        sensitivity.append(
            EvidenceSensitivity(
                scenario_id=f"sensitivity:without_{category}",
                removed_category=category,
                baseline_confidence=baseline_confidence,
                perturbed_confidence=perturbed,
                confidence_delta=delta,
                remaining_evidence_count=len(snapshot.evidence) - len(removed),
                fragile=delta >= 0.08,
                interpretation=(
                    f"Confidence falls by {delta * 100:.1f} points when "
                    f"{category.replace('_', ' ')} "
                    "evidence is removed. This measures dependence, not causal importance."
                ),
            )
        )
    return sorted(sensitivity, key=lambda item: item.confidence_delta, reverse=True)


class ThesisEvaluationService:
    """Evaluate saved theses on future bars without feeding outcomes into thesis creation."""

    def __init__(self, repository: SqlAlchemyDataRepository) -> None:
        self._repository = repository

    def evaluate(self, thesis_id: str) -> ThesisEvaluation | None:
        payload = self._repository.get_thesis_version(thesis_id)
        if payload is None:
            return None
        thesis = ThesisVersion.model_validate(payload)
        bars = self._repository.list_price_bars_as_of(
            symbol=thesis.symbol,
            cutoff=datetime.now(UTC),
            timeframe="1Day",
        )
        base_indexes = [
            index for index, bar in enumerate(bars) if bar.event_time <= thesis.as_of
        ]
        if not base_indexes:
            return None
        base_index = base_indexes[-1]
        base_close = float(bars[base_index].close)
        expected = _expected_direction(thesis.state)
        outcomes: list[ThesisOutcomePoint] = []
        for horizon in (5, 20, 60):
            end_index = base_index + horizon
            if end_index >= len(bars):
                outcomes.append(
                    ThesisOutcomePoint(
                        horizon_trading_days=horizon,
                        available=False,
                        realized_direction="unavailable",
                    )
                )
                continue
            end_bar = bars[end_index]
            realized_return = (float(end_bar.close) / base_close - 1) * 100
            direction: Literal["positive", "negative", "flat", "unavailable"]
            if realized_return > 0.25:
                direction = "positive"
            elif realized_return < -0.25:
                direction = "negative"
            else:
                direction = "flat"
            aligned = direction == expected if expected != "undirected" else None
            outcomes.append(
                ThesisOutcomePoint(
                    horizon_trading_days=horizon,
                    available=True,
                    end_date=end_bar.event_time,
                    realized_return_pct=round(realized_return, 4),
                    realized_direction=direction,
                    thesis_aligned=aligned,
                )
            )
        scored = [item for item in outcomes if item.thesis_aligned is not None]
        aligned_horizons = sum(item.thesis_aligned is True for item in scored)
        return ThesisEvaluation(
            thesis_id=thesis.thesis_id,
            symbol=thesis.symbol,
            version_number=thesis.version_number,
            thesis_cutoff=thesis.cutoff,
            thesis_as_of=thesis.as_of,
            evaluated_at=utc_now(),
            expected_direction=expected,
            outcomes=outcomes,
            scored_horizons=len(scored),
            aligned_horizons=aligned_horizons,
            directional_accuracy=(
                round(aligned_horizons / len(scored), 3) if scored else None
            ),
            methodology=(
                "Evaluation-only realized returns from the 5th, 20th and 60th trading bars after "
                "the saved thesis as_of bar. These future bars are never inputs to thesis "
                "creation. "
                "Constructive expects positive; cautious/at-risk expects negative; neutral is not "
                "directionally scored. A ±0.25% band is treated as flat."
            ),
        )


def _expected_direction(
    state: str,
) -> Literal["positive", "negative", "undirected"]:
    if state == "constructive":
        return "positive"
    if state in {"cautious", "at_risk"}:
        return "negative"
    return "undirected"
