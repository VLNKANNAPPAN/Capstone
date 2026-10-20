from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReturnMetrics(BaseModel):
    one_day_pct: float | None = None
    twenty_day_pct: float | None = None
    sixty_day_pct: float | None = None
    ninety_day_pct: float | None = None


class TrendMetrics(BaseModel):
    sma_20: float | None = None
    sma_50: float | None = None
    sma_200: float | None = None
    ema_20: float | None = None
    distance_sma_20_pct: float | None = None
    distance_52_week_high_pct: float | None = None


class MomentumMetrics(BaseModel):
    rsi_14: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None


class RiskMetrics(BaseModel):
    annualized_volatility_30d_pct: float | None = None
    annualized_volatility_90d_pct: float | None = None
    atr_14: float | None = None
    max_drawdown_252d_pct: float | None = None
    sharpe_252d: float | None = None
    sortino_252d: float | None = None
    cvar_95_daily_pct: float | None = None


class LiquidityMetrics(BaseModel):
    average_volume_20d: float | None = None
    volume_ratio_20d: float | None = None


class TechnicalSnapshot(BaseModel):
    symbol: str
    timeframe: str
    cutoff: datetime
    as_of: datetime
    source: str
    observation_count: int
    close: float
    returns: ReturnMetrics
    trend: TrendMetrics
    momentum: MomentumMetrics
    risk: RiskMetrics
    liquidity: LiquidityMetrics
    signal: str
    methodology: str


class MetricHistoryPoint(BaseModel):
    event_time: datetime
    sharpe: float | None = None
    sortino: float | None = None
    annualized_volatility_pct: float | None = None
    maximum_drawdown_pct: float | None = None


class MetricHistory(BaseModel):
    symbol: str
    timeframe: str
    window: int
    points: list[MetricHistoryPoint]
    methodology: str
