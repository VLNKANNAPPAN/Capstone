from __future__ import annotations

import math
import statistics
from collections import Counter
from datetime import UTC, date, datetime

import httpx

from market_platform.dashboard.models import StockMetric
from market_platform.dashboard.service import DashboardQueryService
from market_platform.db.repository import SqlAlchemyDataRepository
from market_platform.domain.models import ContentType, utc_now
from market_platform.portfolio.groq import GroqPortfolioGenerator
from market_platform.portfolio.models import (
    PortfolioDiversification,
    PortfolioExpectation,
    PortfolioHolding,
    PortfolioNarrative,
    PortfolioProposal,
    PortfolioRequest,
)

SECTORS = {
    "ASIANPAINT.NS": "Consumer discretionary",
    "AXISBANK.NS": "Financial services",
    "BAJFINANCE.NS": "Financial services",
    "BHARTIARTL.NS": "Communication services",
    "HDFCBANK.NS": "Financial services",
    "HINDUNILVR.NS": "Consumer staples",
    "ICICIBANK.NS": "Financial services",
    "INFY.NS": "Information technology",
    "ITC.NS": "Consumer staples",
    "KOTAKBANK.NS": "Financial services",
    "LT.NS": "Industrials",
    "M&M.NS": "Automobiles",
    "MARUTI.NS": "Automobiles",
    "NTPC.NS": "Utilities",
    "RELIANCE.NS": "Energy & diversified",
    "SBIN.NS": "Financial services",
    "SUNPHARMA.NS": "Healthcare",
    "TCS.NS": "Information technology",
    "TITAN.NS": "Consumer discretionary",
    "ULTRACEMCO.NS": "Materials",
}

FACTOR_LABELS = {
    "return_20d": "20-day momentum",
    "return_60d": "60-day momentum",
    "sharpe": "Sharpe efficiency",
    "sortino": "Sortino downside efficiency",
    "volatility": "Low volatility",
    "drawdown": "Drawdown control",
    "tail": "CVaR tail-loss control",
    "trend": "Trend quality",
    "rsi": "RSI balance",
}


class PortfolioProposalService:
    def __init__(
        self,
        *,
        repository: SqlAlchemyDataRepository,
        generator: GroqPortfolioGenerator | None = None,
    ) -> None:
        self._repository = repository
        self._dashboard = DashboardQueryService(repository)
        self._generator = generator

    def propose(self, request: PortfolioRequest) -> PortfolioProposal:
        analytics = self._dashboard.snapshot(limit=1).market_analytics
        stocks = [item for item in analytics.stocks if item.close > 0]
        if not stocks:
            raise ValueError("no stock metrics are available")
        profile = _profile(request.risk_level, request.duration_months)
        factor_weights = {key: value for key, value in profile.items() if key in FACTOR_LABELS}
        dimensions = _dimensions(stocks)
        scored = _score_stocks(stocks, dimensions, factor_weights)
        now = datetime.now(UTC)
        returns_by_symbol = {
            stock.symbol: _daily_returns(self._repository, stock.symbol, now) for stock in stocks
        }
        selected = _select_diversified(
            scored,
            returns_by_symbol,
            count=int(profile["count"]),
            sector_limit=int(profile["sector_limit"]),
            correlation_penalty=profile["correlation_penalty"],
        )
        weights = _allocation_weights(
            selected,
            stock_cap=profile["cap"],
            sector_cap=profile["sector_cap"],
            volatility_bias=profile["volatility_bias"],
        )
        holdings = self._build_holdings(request, selected, weights, now)
        if not holdings:
            raise ValueError("budget is too small to purchase any selected whole share")
        invested_amount = sum(item.invested_amount for item in holdings)
        diversification = _diversification(
            holdings,
            returns_by_symbol,
            request.budget,
            profile["sector_cap"],
        )
        expectation = _expectation(
            request,
            holdings,
            returns_by_symbol,
            diversification,
        )
        narrative: PortfolioNarrative | None = None
        warnings = [
            "The return range is a historical model estimate, not a promise or price target.",
            "Fundamental valuation and audited financial-statement factors are not yet available.",
            "Taxes, brokerage, slippage and future regime changes are not included.",
        ]
        if self._generator is not None:
            try:
                narrative = self._generator.generate(request=request, holdings=holdings)
            except (httpx.HTTPError, KeyError, ValueError):
                warnings.append(
                    "AI explanation was unavailable; deterministic allocation remains valid."
                )
        return PortfolioProposal(
            generated_at=utc_now(),
            budget=request.budget,
            invested_amount=round(invested_amount, 2),
            cash_remaining=round(request.budget - invested_amount, 2),
            risk_level=request.risk_level,
            duration_months=request.duration_months,
            objective=(
                "Build a diversified historical risk-adjusted model portfolio under stock, "
                "sector, correlation and whole-share budget constraints."
            ),
            holdings=holdings,
            weighted_sharpe=_weighted(holdings, "sharpe"),
            weighted_sortino=_weighted(holdings, "sortino"),
            weighted_volatility_pct=_weighted(holdings, "volatility_pct"),
            weighted_maximum_drawdown_pct=_weighted(holdings, "maximum_drawdown_pct"),
            expectation=expectation,
            diversification=diversification,
            factor_weights_pct={
                FACTOR_LABELS[key]: round(value * 100, 1) for key, value in factor_weights.items()
            },
            ai_narrative=narrative,
            warnings=warnings,
            methodology=(
                "Nine normalized factors cover momentum, trend, risk-adjusted return, total "
                "risk and downside risk. Greedy selection applies sector limits and penalizes "
                "correlation with already selected holdings. Inverse-volatility-aware weights "
                "are capped by stock and sector. Groq explains but cannot alter allocation."
            ),
        )

    def _build_holdings(
        self,
        request: PortfolioRequest,
        selected: list[tuple[float, StockMetric]],
        weights: list[float],
        now: datetime,
    ) -> list[PortfolioHolding]:
        holdings: list[PortfolioHolding] = []
        for (score, stock), weight in zip(selected, weights, strict=True):
            target = request.budget * weight
            shares = max(0, math.floor(target / stock.close))
            if shares == 0:
                continue
            invested = shares * stock.close
            content = self._repository.list_content_as_of(
                symbol=stock.symbol,
                cutoff=now,
                limit=20,
            )
            headlines = [
                item.title
                for item in content
                if item.content_type in {ContentType.NEWS, ContentType.VIDEO}
            ][:2]
            holdings.append(
                PortfolioHolding(
                    symbol=stock.symbol,
                    name=stock.name,
                    sector=_sector(stock.symbol),
                    shares=shares,
                    price=stock.close,
                    invested_amount=round(invested, 2),
                    weight_pct=round(invested / request.budget * 100, 2),
                    evidence_score=round(score, 4),
                    signal=stock.signal,
                    sharpe=stock.sharpe_252d,
                    sortino=stock.sortino_252d,
                    volatility_pct=stock.volatility_20d_pct,
                    maximum_drawdown_pct=stock.max_drawdown_252d_pct,
                    return_60d_pct=stock.return_60d_pct,
                    news_headlines=headlines,
                    rationale=_rationale(stock.signal, score, bool(headlines)),
                )
            )
        return holdings


def _dimensions(stocks: list[StockMetric]) -> dict[str, list[float]]:
    return {
        "return_20d": _normalize([item.return_20d_pct for item in stocks]),
        "return_60d": _normalize([item.return_60d_pct for item in stocks]),
        "sharpe": _normalize([item.sharpe_252d for item in stocks]),
        "sortino": _normalize([item.sortino_252d for item in stocks]),
        "volatility": _normalize([-(item.volatility_20d_pct or 100.0) for item in stocks]),
        "drawdown": _normalize([item.max_drawdown_252d_pct for item in stocks]),
        "tail": _normalize([item.cvar_95_daily_pct for item in stocks]),
        "trend": [_trend_quality(item.distance_sma20_pct) for item in stocks],
        "rsi": [_rsi_quality(item.rsi_14) for item in stocks],
    }


def _score_stocks(
    stocks: list[StockMetric],
    dimensions: dict[str, list[float]],
    factor_weights: dict[str, float],
) -> list[tuple[float, StockMetric]]:
    scored: list[tuple[float, StockMetric]] = []
    for index, stock in enumerate(stocks):
        score = sum(factor_weights[metric] * dimensions[metric][index] for metric in factor_weights)
        if stock.signal == "extended":
            score -= 0.07
        scored.append((score, stock))
    return sorted(scored, key=lambda item: item[0], reverse=True)


def _select_diversified(
    scored: list[tuple[float, StockMetric]],
    returns_by_symbol: dict[str, dict[date, float]],
    *,
    count: int,
    sector_limit: int,
    correlation_penalty: float,
) -> list[tuple[float, StockMetric]]:
    selected: list[tuple[float, StockMetric]] = []
    remaining = scored[:]
    sector_counts: Counter[str] = Counter()
    while remaining and len(selected) < count:
        eligible = [
            item for item in remaining if sector_counts[_sector(item[1].symbol)] < sector_limit
        ]
        if not eligible:
            eligible = remaining

        def adjusted(item: tuple[float, StockMetric]) -> float:
            score, stock = item
            correlations = [
                max(
                    0.0,
                    _correlation(
                        returns_by_symbol[stock.symbol],
                        returns_by_symbol[chosen.symbol],
                    )
                    or 0.0,
                )
                for _, chosen in selected
            ]
            average = statistics.fmean(correlations) if correlations else 0.0
            return score - correlation_penalty * average

        chosen = max(eligible, key=adjusted)
        selected.append(chosen)
        sector_counts[_sector(chosen[1].symbol)] += 1
        remaining.remove(chosen)
    return selected


def _allocation_weights(
    selected: list[tuple[float, StockMetric]],
    *,
    stock_cap: float,
    sector_cap: float,
    volatility_bias: float,
) -> list[float]:
    raw = [
        max(score, 0.05) * (20.0 / max(stock.volatility_20d_pct or 20.0, 5.0)) ** volatility_bias
        for score, stock in selected
    ]
    total = sum(raw)
    weights = _cap_and_normalize([value / total for value in raw], stock_cap)
    return _cap_sector_weights(weights, selected, sector_cap)


def _profile(risk: str, months: int) -> dict[str, float]:
    if risk == "conservative":
        profile = {
            "return_20d": 0.04,
            "return_60d": 0.06,
            "sharpe": 0.18,
            "sortino": 0.18,
            "volatility": 0.18,
            "drawdown": 0.14,
            "tail": 0.14,
            "trend": 0.05,
            "rsi": 0.03,
            "count": 8.0,
            "cap": 0.18,
            "sector_cap": 0.25,
            "sector_limit": 1.0,
            "correlation_penalty": 0.24,
            "volatility_bias": 1.0,
        }
    elif risk == "aggressive":
        profile = {
            "return_20d": 0.12,
            "return_60d": 0.28,
            "sharpe": 0.14,
            "sortino": 0.10,
            "volatility": 0.06,
            "drawdown": 0.08,
            "tail": 0.07,
            "trend": 0.10,
            "rsi": 0.05,
            "count": 5.0,
            "cap": 0.30,
            "sector_cap": 0.45,
            "sector_limit": 2.0,
            "correlation_penalty": 0.10,
            "volatility_bias": 0.15,
        }
    else:
        profile = {
            "return_20d": 0.08,
            "return_60d": 0.16,
            "sharpe": 0.16,
            "sortino": 0.14,
            "volatility": 0.12,
            "drawdown": 0.10,
            "tail": 0.10,
            "trend": 0.08,
            "rsi": 0.06,
            "count": 6.0,
            "cap": 0.22,
            "sector_cap": 0.35,
            "sector_limit": 2.0,
            "correlation_penalty": 0.17,
            "volatility_bias": 0.50,
        }
    if months <= 6:
        shift = min(profile["return_60d"], 0.04)
        profile["return_60d"] -= shift
        profile["return_20d"] += shift * 0.65
        profile["trend"] += shift * 0.35
    elif months >= 36:
        shift = min(profile["return_20d"], 0.03)
        profile["return_20d"] -= shift
        profile["sharpe"] += shift * 0.5
        profile["drawdown"] += shift * 0.5
    return profile


def _expectation(
    request: PortfolioRequest,
    holdings: list[PortfolioHolding],
    returns_by_symbol: dict[str, dict[date, float]],
    diversification: PortfolioDiversification,
) -> PortfolioExpectation:
    series = _portfolio_return_series(request.budget, holdings, returns_by_symbol)
    observation_count = len(series)
    sample_mean = statistics.fmean(series) * 252 if series else 0.0
    annual_volatility = statistics.stdev(series) * math.sqrt(252) if len(series) >= 2 else 0.25
    prior = {"conservative": 0.08, "balanced": 0.10, "aggressive": 0.12}[request.risk_level]
    data_weight = min(observation_count / 252, 1.0) * 0.35
    annual_central = _clamp(
        prior * (1 - data_weight) + sample_mean * data_weight,
        -0.05,
        0.25,
    )
    years = request.duration_months / 12
    central = (1 + annual_central) ** years - 1
    metric_fields = (
        "sharpe",
        "sortino",
        "volatility_pct",
        "maximum_drawdown_pct",
        "return_60d_pct",
    )
    coverage = statistics.fmean(
        sum(getattr(item, field) is not None for field in metric_fields) / len(metric_fields)
        for item in holdings
    )
    sample_score = min(observation_count / 252, 1.0)
    sector_score = min(diversification.sector_count / min(len(holdings), 6), 1.0)
    concentration_score = min(
        diversification.effective_holdings / max(len(holdings), 1),
        1.0,
    )
    confidence = round(
        min(
            80.0,
            100
            * (
                0.30 * sample_score
                + 0.25 * coverage
                + 0.25 * sector_score
                + 0.20 * concentration_score
            ),
        )
    )
    uncertainty_scale = 1.25 - confidence / 200
    uncertainty = 0.84 * annual_volatility * math.sqrt(years) * uncertainty_scale
    low = _clamp(central - uncertainty, -0.80, 1.50)
    high = _clamp(central + uncertainty, -0.80, 1.50)
    label = "Higher" if confidence >= 70 else "Moderate" if confidence >= 50 else "Low"
    return PortfolioExpectation(
        horizon_months=request.duration_months,
        low_return_pct=round(low * 100, 2),
        central_return_pct=round(central * 100, 2),
        high_return_pct=round(high * 100, 2),
        low_value=round(request.budget * (1 + low), 2),
        central_value=round(request.budget * (1 + central), 2),
        high_value=round(request.budget * (1 + high), 2),
        confidence_score=confidence,
        confidence_label=label,
        observation_count=observation_count,
        assumptions=[
            "Uses up to 252 stored daily observations and a shrunk long-run equity prior.",
            "The displayed band is a model uncertainty range, not a guaranteed "
            "probability interval.",
            "Future returns, correlations and volatility can differ materially from history.",
        ],
    )


def _diversification(
    holdings: list[PortfolioHolding],
    returns_by_symbol: dict[str, dict[date, float]],
    budget: float,
    sector_cap: float,
) -> PortfolioDiversification:
    sector_allocations: dict[str, float] = {}
    for item in holdings:
        sector_allocations[item.sector] = sector_allocations.get(item.sector, 0.0) + (
            item.invested_amount / budget * 100
        )
    invested = sum(item.invested_amount for item in holdings)
    normalized = [item.invested_amount / invested for item in holdings]
    effective = 1 / sum(weight**2 for weight in normalized)
    correlations = [
        value
        for index, left in enumerate(holdings)
        for right in holdings[index + 1 :]
        if (
            value := _correlation(
                returns_by_symbol[left.symbol],
                returns_by_symbol[right.symbol],
            )
        )
        is not None
    ]
    return PortfolioDiversification(
        sector_count=len(sector_allocations),
        sector_allocations_pct={
            sector: round(weight, 2) for sector, weight in sorted(sector_allocations.items())
        },
        effective_holdings=round(effective, 2),
        average_pairwise_correlation=(
            round(statistics.fmean(correlations), 4) if correlations else None
        ),
        maximum_sector_weight_pct=round(sector_cap * 100, 1),
    )


def _daily_returns(
    repository: SqlAlchemyDataRepository,
    symbol: str,
    cutoff: datetime,
) -> dict[date, float]:
    bars = repository.list_price_bars_as_of(
        symbol=symbol,
        cutoff=cutoff,
        timeframe="1Day",
    )[-253:]
    return {
        bars[index].event_time.date(): float(bars[index].close / bars[index - 1].close - 1)
        for index in range(1, len(bars))
        if bars[index - 1].close > 0
    }


def _portfolio_return_series(
    budget: float,
    holdings: list[PortfolioHolding],
    returns_by_symbol: dict[str, dict[date, float]],
) -> list[float]:
    date_sets = [set(returns_by_symbol[item.symbol]) for item in holdings]
    if not date_sets:
        return []
    common_dates = sorted(set.intersection(*date_sets))
    invested_weight = sum(item.invested_amount for item in holdings) / budget
    cash_weight = max(0.0, 1 - invested_weight)
    daily_cash_return = 0.065 / 252
    return [
        sum(
            item.invested_amount / budget * returns_by_symbol[item.symbol][day] for item in holdings
        )
        + cash_weight * daily_cash_return
        for day in common_dates
    ]


def _correlation(left: dict[date, float], right: dict[date, float]) -> float | None:
    dates = sorted(set(left).intersection(right))
    if len(dates) < 20:
        return None
    left_values = [left[day] for day in dates]
    right_values = [right[day] for day in dates]
    left_mean = statistics.fmean(left_values)
    right_mean = statistics.fmean(right_values)
    numerator = sum(
        (left_value - left_mean) * (right_value - right_mean)
        for left_value, right_value in zip(left_values, right_values, strict=True)
    )
    denominator = math.sqrt(
        sum((value - left_mean) ** 2 for value in left_values)
        * sum((value - right_mean) ** 2 for value in right_values)
    )
    return numerator / denominator if denominator else None


def _cap_sector_weights(
    weights: list[float],
    selected: list[tuple[float, StockMetric]],
    cap: float,
) -> list[float]:
    result = weights[:]
    sectors = [_sector(stock.symbol) for _, stock in selected]
    for _ in range(20):
        totals = {
            sector: sum(result[index] for index, value in enumerate(sectors) if value == sector)
            for sector in set(sectors)
        }
        over = {sector: total for sector, total in totals.items() if total > cap + 1e-9}
        if not over:
            break
        excess = 0.0
        for sector, total in over.items():
            scale = cap / total
            for index, value in enumerate(sectors):
                if value == sector:
                    before = result[index]
                    result[index] *= scale
                    excess += before - result[index]
        eligible = [index for index, sector in enumerate(sectors) if sector not in over]
        base = sum(result[index] for index in eligible)
        if not eligible:
            break
        for index in eligible:
            result[index] += excess * (result[index] / base if base else 1 / len(eligible))
    total = sum(result)
    return [value / total for value in result]


def _normalize(values: list[float | None]) -> list[float]:
    clean = [value for value in values if value is not None]
    if not clean:
        return [0.5 for _ in values]
    low, high = min(clean), max(clean)
    if math.isclose(low, high):
        return [0.5 for _ in values]
    return [0.5 if value is None else (value - low) / (high - low) for value in values]


def _cap_and_normalize(weights: list[float], cap: float) -> list[float]:
    result = weights[:]
    for _ in range(20):
        excess = sum(max(0.0, value - cap) for value in result)
        result = [min(value, cap) for value in result]
        eligible = [index for index, value in enumerate(result) if value < cap]
        if excess < 1e-9 or not eligible:
            break
        base = sum(result[index] for index in eligible)
        for index in eligible:
            result[index] += excess * (result[index] / base if base else 1 / len(eligible))
    total = sum(result)
    return [value / total for value in result]


def _weighted(holdings: list[PortfolioHolding], field: str) -> float | None:
    pairs = [
        (float(getattr(item, field)), item.invested_amount)
        for item in holdings
        if getattr(item, field) is not None
    ]
    total = sum(weight for _, weight in pairs)
    return round(sum(value * weight for value, weight in pairs) / total, 4) if total else None


def _trend_quality(value: float | None) -> float:
    return 0.5 if value is None else max(0.0, 1 - abs(value - 3.0) / 18.0)


def _rsi_quality(value: float | None) -> float:
    return 0.5 if value is None else max(0.0, 1 - abs(value - 55.0) / 45.0)


def _sector(symbol: str) -> str:
    return SECTORS.get(symbol, "Other")


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _rationale(signal: str, score: float, has_content: bool) -> str:
    context = "linked headlines are available" if has_content else "news coverage is limited"
    return (
        "Selected after multi-factor, sector and correlation controls "
        f"(evidence score {score:.2f}); regime is {signal}; {context}."
    )
