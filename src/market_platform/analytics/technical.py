from __future__ import annotations

import math
import statistics
from datetime import UTC, datetime

from market_platform.analytics.models import (
    LiquidityMetrics,
    MetricHistory,
    MetricHistoryPoint,
    MomentumMetrics,
    ReturnMetrics,
    RiskMetrics,
    TechnicalSnapshot,
    TrendMetrics,
)
from market_platform.db.repository import SqlAlchemyDataRepository
from market_platform.domain.models import PriceBar, ensure_utc

TRADING_DAYS_PER_YEAR = 252
DEFAULT_ANNUAL_RISK_FREE_RATE = 0.065


class TechnicalAnalyticsService:
    """Calculate reproducible indicators using only data available at the cutoff."""

    def __init__(self, repository: SqlAlchemyDataRepository) -> None:
        self._repository = repository

    def snapshot(
        self,
        *,
        symbol: str,
        cutoff: datetime | None = None,
        timeframe: str = "1Day",
    ) -> TechnicalSnapshot | None:
        point_in_time = ensure_utc(cutoff) if cutoff else datetime.now(UTC)
        bars = self._repository.list_price_bars_as_of(
            symbol=symbol,
            cutoff=point_in_time,
            timeframe=timeframe,
        )
        if not bars:
            return None
        return calculate_technical_snapshot(
            bars,
            symbol=symbol.strip().upper(),
            timeframe=timeframe,
            cutoff=point_in_time,
        )

    def metric_history(
        self,
        *,
        symbol: str,
        cutoff: datetime | None = None,
        timeframe: str = "1Day",
        window: int = 60,
        step: int = 5,
    ) -> MetricHistory:
        point_in_time = ensure_utc(cutoff) if cutoff else datetime.now(UTC)
        bars = self._repository.list_price_bars_as_of(
            symbol=symbol,
            cutoff=point_in_time,
            timeframe=timeframe,
        )
        points: list[MetricHistoryPoint] = []
        minimum = max(60, window)
        for end in range(minimum, len(bars) + 1, max(1, step)):
            sample = bars[max(0, end - window - 1) : end]
            prices = [float(bar.close) for bar in sample]
            returns = [prices[index] / prices[index - 1] - 1 for index in range(1, len(prices))]
            sharpe, sortino = _risk_adjusted_ratios(returns)
            points.append(
                MetricHistoryPoint(
                    event_time=sample[-1].event_time,
                    sharpe=sharpe,
                    sortino=sortino,
                    annualized_volatility_pct=_annualized_volatility(
                        returns, min(window, len(returns))
                    ),
                    maximum_drawdown_pct=_max_drawdown(prices),
                )
            )
        if bars and (not points or points[-1].event_time != bars[-1].event_time):
            sample = bars[-(window + 1) :]
            prices = [float(bar.close) for bar in sample]
            returns = [prices[index] / prices[index - 1] - 1 for index in range(1, len(prices))]
            sharpe, sortino = _risk_adjusted_ratios(returns)
            points.append(
                MetricHistoryPoint(
                    event_time=sample[-1].event_time,
                    sharpe=sharpe,
                    sortino=sortino,
                    annualized_volatility_pct=_annualized_volatility(
                        returns, min(window, len(returns))
                    ),
                    maximum_drawdown_pct=_max_drawdown(prices),
                )
            )
        return MetricHistory(
            symbol=symbol.strip().upper(),
            timeframe=timeframe,
            window=window,
            points=points,
            methodology=(
                f"Rolling {window}-trading-day metrics sampled every {step} observations. "
                "Sharpe and Sortino use a 6.5% annual risk-free assumption. These are daily "
                "historical calculations, not live intraday measures or forecasts."
            ),
        )


def calculate_technical_snapshot(
    bars: list[PriceBar],
    *,
    symbol: str,
    timeframe: str,
    cutoff: datetime,
) -> TechnicalSnapshot:
    prices = [float(bar.close) for bar in bars]
    highs = [float(bar.high) for bar in bars]
    lows = [float(bar.low) for bar in bars]
    volumes = [float(bar.volume) for bar in bars]
    returns = [prices[index] / prices[index - 1] - 1 for index in range(1, len(prices))]

    sma_20 = _mean_window(prices, 20)
    rsi_14 = _rsi(prices, 14)
    macd, macd_signal, macd_histogram = _macd(prices)
    sharpe, sortino = _risk_adjusted_ratios(returns)
    average_volume = _mean_window(volumes, 20)
    volume_ratio = volumes[-1] / average_volume if average_volume else None
    high_52_week = max(highs[-TRADING_DAYS_PER_YEAR:])
    distance_sma_20 = ((prices[-1] / sma_20) - 1) * 100 if sma_20 else None

    return TechnicalSnapshot(
        symbol=symbol,
        timeframe=timeframe,
        cutoff=cutoff,
        as_of=bars[-1].event_time,
        source=bars[-1].source,
        observation_count=len(bars),
        close=prices[-1],
        returns=ReturnMetrics(
            one_day_pct=_period_return(prices, 1),
            twenty_day_pct=_period_return(prices, 20),
            sixty_day_pct=_period_return(prices, 60),
            ninety_day_pct=_period_return(prices, 90),
        ),
        trend=TrendMetrics(
            sma_20=sma_20,
            sma_50=_mean_window(prices, 50),
            sma_200=_mean_window(prices, 200),
            ema_20=_ema(prices, 20)[-1] if len(prices) >= 20 else None,
            distance_sma_20_pct=distance_sma_20,
            distance_52_week_high_pct=(prices[-1] / high_52_week - 1) * 100,
        ),
        momentum=MomentumMetrics(
            rsi_14=rsi_14,
            macd=macd,
            macd_signal=macd_signal,
            macd_histogram=macd_histogram,
        ),
        risk=RiskMetrics(
            annualized_volatility_30d_pct=_annualized_volatility(returns, 30),
            annualized_volatility_90d_pct=_annualized_volatility(returns, 90),
            atr_14=_atr(highs, lows, prices, 14),
            max_drawdown_252d_pct=_max_drawdown(prices[-253:]),
            sharpe_252d=sharpe,
            sortino_252d=sortino,
            cvar_95_daily_pct=_historical_cvar(returns),
        ),
        liquidity=LiquidityMetrics(
            average_volume_20d=average_volume,
            volume_ratio_20d=volume_ratio,
        ),
        signal=_signal(_period_return(prices, 60), distance_sma_20, rsi_14),
        methodology=(
            "Deterministic price/volume indicators computed from point-in-time daily bars. "
            "Sharpe and Sortino use a 6.5% annual risk-free assumption. Missing history is "
            "reported as null; values are evidence, not forecasts or trade advice."
        ),
    )


def _period_return(values: list[float], periods: int) -> float | None:
    if len(values) <= periods or values[-periods - 1] == 0:
        return None
    return (values[-1] / values[-periods - 1] - 1) * 100


def _mean_window(values: list[float], periods: int) -> float | None:
    return statistics.fmean(values[-periods:]) if len(values) >= periods else None


def _ema(values: list[float], periods: int) -> list[float]:
    if not values:
        return []
    multiplier = 2 / (periods + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append((value - result[-1]) * multiplier + result[-1])
    return result


def _macd(values: list[float]) -> tuple[float | None, float | None, float | None]:
    if len(values) < 35:
        return None, None, None
    fast = _ema(values, 12)
    slow = _ema(values, 26)
    line = [fast[index] - slow[index] for index in range(len(values))]
    signal = _ema(line, 9)
    return line[-1], signal[-1], line[-1] - signal[-1]


def _rsi(values: list[float], periods: int) -> float | None:
    if len(values) <= periods:
        return None
    changes = [values[index] - values[index - 1] for index in range(1, len(values))]
    window = changes[-periods:]
    gains = statistics.fmean(max(change, 0) for change in window)
    losses = statistics.fmean(max(-change, 0) for change in window)
    if losses == 0:
        return 100.0
    return 100 - (100 / (1 + gains / losses))


def _annualized_volatility(returns: list[float], periods: int) -> float | None:
    if len(returns) < periods:
        return None
    return statistics.stdev(returns[-periods:]) * math.sqrt(TRADING_DAYS_PER_YEAR) * 100


def _atr(highs: list[float], lows: list[float], closes: list[float], periods: int) -> float | None:
    if len(closes) <= periods:
        return None
    true_ranges = [
        max(
            highs[index] - lows[index],
            abs(highs[index] - closes[index - 1]),
            abs(lows[index] - closes[index - 1]),
        )
        for index in range(1, len(closes))
    ]
    return statistics.fmean(true_ranges[-periods:])


def _max_drawdown(values: list[float]) -> float | None:
    if not values:
        return None
    peak = values[0]
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        worst = min(worst, value / peak - 1)
    return worst * 100


def _risk_adjusted_ratios(
    returns: list[float],
    annual_risk_free_rate: float = DEFAULT_ANNUAL_RISK_FREE_RATE,
) -> tuple[float | None, float | None]:
    window = returns[-TRADING_DAYS_PER_YEAR:]
    if len(window) < 60:
        return None, None
    daily_risk_free = (1 + annual_risk_free_rate) ** (1 / TRADING_DAYS_PER_YEAR) - 1
    excess = [value - daily_risk_free for value in window]
    mean_excess = statistics.fmean(excess)
    volatility = statistics.stdev(window)
    downside = math.sqrt(statistics.fmean(min(value, 0) ** 2 for value in excess))
    sharpe = mean_excess / volatility * math.sqrt(TRADING_DAYS_PER_YEAR) if volatility else None
    sortino = mean_excess / downside * math.sqrt(TRADING_DAYS_PER_YEAR) if downside else None
    return sharpe, sortino


def _historical_cvar(returns: list[float], confidence: float = 0.95) -> float | None:
    window = returns[-TRADING_DAYS_PER_YEAR:]
    if len(window) < 20:
        return None
    tail_count = max(1, math.ceil(len(window) * (1 - confidence)))
    return statistics.fmean(sorted(window)[:tail_count]) * 100


def _signal(return_60d: float | None, distance_sma_20: float | None, rsi: float | None) -> str:
    if rsi is not None and rsi >= 70:
        return "extended"
    if rsi is not None and rsi <= 30:
        return "oversold"
    if return_60d is not None and distance_sma_20 is not None:
        if return_60d > 0 and distance_sma_20 > 0:
            return "positive trend"
        if return_60d < 0 and distance_sma_20 < 0:
            return "negative trend"
    return "mixed"
