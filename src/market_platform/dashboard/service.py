from __future__ import annotations

import math
import statistics
from datetime import UTC, datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, sessionmaker

from market_platform.dashboard.models import (
    AssetSummary,
    ContentSummary,
    DashboardSnapshot,
    DatasetCounts,
    FilingSummary,
    LatestPrice,
    MarketAnalytics,
    MarketBreadth,
    PricePoint,
    PriceSeries,
    QualityIssueSummary,
    RunSummary,
    SourceSummary,
    StockMetric,
)
from market_platform.db.models import (
    AcquisitionRunRow,
    AssetRow,
    BondSecurityRow,
    ContentItemRow,
    CorporateDisclosureRow,
    DataQualityIssueRow,
    FundamentalDocumentRow,
    MacroObservationRow,
    PriceBarRow,
    RawRecordRow,
    YieldCurvePointRow,
)
from market_platform.db.repository import SqlAlchemyDataRepository, _db_time
from market_platform.domain.models import ensure_utc, utc_now

TRADING_DAYS_PER_YEAR = 252
ANNUAL_RISK_FREE_RATE = 0.065


class DashboardQueryService:
    def __init__(self, repository: SqlAlchemyDataRepository) -> None:
        self._sessions = sessionmaker(repository.engine, expire_on_commit=False)

    def snapshot(self, *, limit: int = 12) -> DashboardSnapshot:
        with self._sessions() as session:
            counts = self._counts(session)
            latest_ingested_at = session.scalar(select(func.max(RawRecordRow.ingested_at)))
            assets = self._assets(session)
            sources = self._sources(session)
            latest_prices = self._latest_prices(session)
            recent_runs = self._recent_runs(session, limit)
            issues = self._quality_issues(session, limit)
            filings = self._recent_filings(session, limit)
            market_analytics = self._market_analytics(session)
            recent_content = self._recent_content(session, limit)

        return DashboardSnapshot(
            generated_at=utc_now(),
            latest_ingested_at=(
                _db_time(latest_ingested_at) if latest_ingested_at is not None else None
            ),
            counts=counts,
            assets=assets,
            sources=sources,
            latest_prices=latest_prices,
            recent_runs=recent_runs,
            quality_issues=issues,
            recent_filings=filings,
            market_analytics=market_analytics,
            recent_content=recent_content,
        )

    def price_series(
        self,
        *,
        symbol: str,
        cutoff: datetime | None = None,
        timeframe: str | None = None,
        limit: int = 250,
    ) -> PriceSeries:
        point_in_time = ensure_utc(cutoff) if cutoff else datetime.now(UTC)
        statement: Select[tuple[PriceBarRow]] = (
            select(PriceBarRow)
            .where(PriceBarRow.symbol == symbol.strip().upper())
            .where(PriceBarRow.available_at <= point_in_time)
            .order_by(PriceBarRow.event_time.desc())
            .limit(limit)
        )
        if timeframe:
            statement = statement.where(PriceBarRow.timeframe == timeframe)
        with self._sessions() as session:
            rows = list(reversed(session.scalars(statement).all()))
        return PriceSeries(
            symbol=symbol.strip().upper(),
            timeframe=timeframe,
            cutoff=point_in_time,
            points=[
                PricePoint(
                    event_time=_db_time(row.event_time),
                    available_at=_db_time(row.available_at),
                    open=float(row.open),
                    high=float(row.high),
                    low=float(row.low),
                    close=float(row.close),
                    volume=float(row.volume),
                )
                for row in rows
            ],
        )

    @staticmethod
    def _counts(session: Session) -> DatasetCounts:
        return DatasetCounts(
            assets=(
                session.scalar(
                    select(func.count()).select_from(AssetRow).where(AssetRow.active.is_(True))
                )
                or 0
            ),
            price_bars=session.scalar(select(func.count()).select_from(PriceBarRow)) or 0,
            filings=(session.scalar(select(func.count()).select_from(FundamentalDocumentRow)) or 0),
            raw_records=session.scalar(select(func.count()).select_from(RawRecordRow)) or 0,
            quality_issues=(
                session.scalar(select(func.count()).select_from(DataQualityIssueRow)) or 0
            ),
            news_items=(
                session.scalar(
                    select(func.count())
                    .select_from(ContentItemRow)
                    .where(ContentItemRow.content_type == "news")
                )
                or 0
            ),
            social_items=(
                session.scalar(
                    select(func.count())
                    .select_from(ContentItemRow)
                    .where(ContentItemRow.content_type == "social")
                )
                or 0
            ),
            video_items=(
                session.scalar(
                    select(func.count())
                    .select_from(ContentItemRow)
                    .where(ContentItemRow.content_type == "video")
                )
                or 0
            ),
            corporate_disclosures=(
                session.scalar(select(func.count()).select_from(CorporateDisclosureRow)) or 0
            ),
            macro_observations=(
                session.scalar(select(func.count()).select_from(MacroObservationRow)) or 0
            ),
            bond_securities=(
                session.scalar(select(func.count()).select_from(BondSecurityRow)) or 0
            ),
            yield_curve_points=(
                session.scalar(select(func.count()).select_from(YieldCurvePointRow)) or 0
            ),
        )

    @staticmethod
    def _assets(session: Session) -> list[AssetSummary]:
        rows = session.scalars(
            select(AssetRow).where(AssetRow.active.is_(True)).order_by(AssetRow.symbol)
        ).all()
        return [
            AssetSummary(
                symbol=row.symbol,
                name=row.name,
                asset_type=row.asset_type,
                exchange=row.exchange,
                currency=row.currency,
                cik=row.cik,
                active=row.active,
            )
            for row in rows
        ]

    @staticmethod
    def _sources(session: Session) -> list[SourceSummary]:
        aggregate_rows = session.execute(
            select(
                RawRecordRow.source,
                RawRecordRow.dataset,
                func.count(RawRecordRow.id),
                func.max(RawRecordRow.available_at),
                func.max(RawRecordRow.ingested_at),
            )
            .group_by(RawRecordRow.source, RawRecordRow.dataset)
            .order_by(RawRecordRow.source, RawRecordRow.dataset)
        ).all()
        latest_status: dict[tuple[str, str], str] = {}
        run_rows = session.scalars(
            select(AcquisitionRunRow).order_by(AcquisitionRunRow.started_at.desc())
        ).all()
        for row in run_rows:
            latest_status.setdefault((row.source, row.dataset), row.status)
        return [
            SourceSummary(
                source=source,
                dataset=dataset,
                record_count=count,
                latest_available_at=_db_time(latest_available),
                latest_ingested_at=_db_time(latest_ingested),
                latest_run_status=latest_status.get((source, dataset)),
            )
            for source, dataset, count, latest_available, latest_ingested in aggregate_rows
        ]

    @staticmethod
    def _latest_prices(session: Session) -> list[LatestPrice]:
        ranked = select(
            PriceBarRow,
            func.row_number()
            .over(partition_by=PriceBarRow.symbol, order_by=PriceBarRow.event_time.desc())
            .label("rank"),
        ).subquery()
        rows = session.execute(select(ranked).where(ranked.c.rank == 1)).mappings().all()
        return [
            LatestPrice(
                symbol=str(row["symbol"]),
                timeframe=str(row["timeframe"]),
                event_time=_db_time(row["event_time"]),
                available_at=_db_time(row["available_at"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
                source=str(row["source"]),
            )
            for row in rows
        ]

    @staticmethod
    def _recent_runs(session: Session, limit: int) -> list[RunSummary]:
        rows = session.scalars(
            select(AcquisitionRunRow).order_by(AcquisitionRunRow.started_at.desc()).limit(limit)
        ).all()
        return [
            RunSummary(
                run_id=row.id,
                source=row.source,
                dataset=row.dataset,
                partition_key=row.partition_key,
                status=row.status,
                started_at=_db_time(row.started_at),
                completed_at=_db_time(row.completed_at) if row.completed_at else None,
                raw_count=row.raw_count,
                accepted_count=row.accepted_count,
                rejected_count=row.rejected_count,
                error_message=row.error_message,
            )
            for row in rows
        ]

    @staticmethod
    def _quality_issues(session: Session, limit: int) -> list[QualityIssueSummary]:
        rows = session.scalars(
            select(DataQualityIssueRow)
            .order_by(DataQualityIssueRow.detected_at.desc())
            .limit(limit)
        ).all()
        return [
            QualityIssueSummary(
                issue_id=row.id,
                source=row.source,
                dataset=row.dataset,
                partition_key=row.partition_key,
                natural_key=row.natural_key,
                code=row.code,
                message=row.message,
                severity=row.severity,
                detected_at=_db_time(row.detected_at),
            )
            for row in rows
        ]

    @staticmethod
    def _recent_filings(session: Session, limit: int) -> list[FilingSummary]:
        rows = session.scalars(
            select(FundamentalDocumentRow)
            .order_by(FundamentalDocumentRow.available_at.desc())
            .limit(limit)
        ).all()
        return [
            FilingSummary(
                symbol=row.symbol,
                form=row.form,
                accession_number=row.accession_number,
                filing_date=row.filing_date,
                report_date=row.report_date,
                available_at=_db_time(row.available_at),
                source_url=row.source_url,
            )
            for row in rows
        ]

    @staticmethod
    def _recent_content(session: Session, limit: int) -> list[ContentSummary]:
        rows = session.scalars(
            select(ContentItemRow).order_by(ContentItemRow.published_at.desc()).limit(limit)
        ).all()
        return [
            ContentSummary(
                source=row.source,
                external_id=row.external_id,
                content_type=row.content_type,
                title=row.title,
                url=row.url,
                published_at=_db_time(row.published_at),
                available_at=_db_time(row.available_at),
                symbols=list(row.symbols),
                sentiment_score=(
                    float(row.sentiment_score) if row.sentiment_score is not None else None
                ),
            )
            for row in rows
        ]

    @staticmethod
    def _market_analytics(session: Session) -> MarketAnalytics:
        asset_rows = {
            row.symbol: row
            for row in session.scalars(select(AssetRow).where(AssetRow.active.is_(True))).all()
        }
        bar_rows = session.scalars(
            select(PriceBarRow)
            .where(PriceBarRow.timeframe == "1Day")
            .order_by(PriceBarRow.symbol, PriceBarRow.event_time)
        ).all()
        grouped: dict[str, list[PriceBarRow]] = {}
        for row in bar_rows:
            grouped.setdefault(row.symbol, []).append(row)

        metrics: list[StockMetric] = []
        for symbol, rows in grouped.items():
            if not rows:
                continue
            prices = [float(row.close) for row in rows]
            volumes = [float(row.volume) for row in rows]
            returns = [prices[index] / prices[index - 1] - 1 for index in range(1, len(prices))]
            return_20d = _period_return(prices, 20)
            return_60d = _period_return(prices, 60)
            volatility = (
                statistics.stdev(returns[-20:]) * math.sqrt(TRADING_DAYS_PER_YEAR) * 100
                if len(returns) >= 20
                else None
            )
            drawdown = _max_drawdown(prices[-253:]) if len(prices) >= 2 else None
            sharpe, sortino = _risk_adjusted_ratios(returns)
            cvar = _historical_cvar(returns)
            sma20 = statistics.fmean(prices[-20:]) if len(prices) >= 20 else None
            distance_sma = ((prices[-1] / sma20) - 1) * 100 if sma20 else None
            rsi = _rsi(prices, 14)
            average_volume = statistics.fmean(volumes[-20:]) if volumes else None
            asset = asset_rows.get(symbol)
            metrics.append(
                StockMetric(
                    symbol=symbol,
                    name=asset.name if asset else None,
                    currency=asset.currency if asset else "USD",
                    as_of=_db_time(rows[-1].event_time),
                    close=prices[-1],
                    return_20d_pct=return_20d,
                    return_60d_pct=return_60d,
                    volatility_20d_pct=volatility,
                    max_drawdown_252d_pct=drawdown,
                    sharpe_252d=sharpe,
                    sortino_252d=sortino,
                    cvar_95_daily_pct=cvar,
                    distance_sma20_pct=distance_sma,
                    rsi_14=rsi,
                    average_volume_20d=average_volume,
                    observation_count=len(rows),
                    signal=_signal(return_60d, distance_sma, rsi),
                )
            )
        metrics.sort(
            key=lambda item: item.return_60d_pct if item.return_60d_pct is not None else -math.inf,
            reverse=True,
        )
        valid_returns = [item.return_20d_pct for item in metrics if item.return_20d_pct is not None]
        valid_volatility = [
            item.volatility_20d_pct for item in metrics if item.volatility_20d_pct is not None
        ]
        valid_sharpe = [item.sharpe_252d for item in metrics if item.sharpe_252d is not None]
        valid_cvar = [
            item.cvar_95_daily_pct for item in metrics if item.cvar_95_daily_pct is not None
        ]
        return MarketAnalytics(
            methodology=(
                "Price-derived indicators only. Sharpe and Sortino use a 6.5% annual risk-free "
                "assumption and up to 252 trading days; CVaR is the mean of the worst 5% of "
                "daily returns. Fundamental metrics are withheld until an auditable statements "
                "source is connected. Values are not forecasts or trade advice."
            ),
            breadth=MarketBreadth(
                covered_assets=len(metrics),
                positive_20d=sum((item.return_20d_pct or 0) > 0 for item in metrics),
                positive_60d=sum((item.return_60d_pct or 0) > 0 for item in metrics),
                above_sma20=sum((item.distance_sma20_pct or 0) > 0 for item in metrics),
                median_return_20d_pct=(statistics.median(valid_returns) if valid_returns else None),
                median_volatility_20d_pct=(
                    statistics.median(valid_volatility) if valid_volatility else None
                ),
                median_sharpe_252d=(statistics.median(valid_sharpe) if valid_sharpe else None),
                median_cvar_95_daily_pct=(statistics.median(valid_cvar) if valid_cvar else None),
            ),
            stocks=metrics,
        )


def _period_return(prices: list[float], periods: int) -> float | None:
    if len(prices) <= periods or prices[-periods - 1] == 0:
        return None
    return (prices[-1] / prices[-periods - 1] - 1) * 100


def _max_drawdown(prices: list[float]) -> float | None:
    if not prices:
        return None
    peak = prices[0]
    worst = 0.0
    for price in prices:
        peak = max(peak, price)
        worst = min(worst, price / peak - 1)
    return worst * 100


def _risk_adjusted_ratios(
    returns: list[float], annual_risk_free_rate: float = ANNUAL_RISK_FREE_RATE
) -> tuple[float | None, float | None]:
    window = returns[-TRADING_DAYS_PER_YEAR:]
    if len(window) < 60:
        return None, None
    daily_risk_free = (1 + annual_risk_free_rate) ** (1 / TRADING_DAYS_PER_YEAR) - 1
    excess_returns = [daily_return - daily_risk_free for daily_return in window]
    mean_excess = statistics.fmean(excess_returns)
    volatility = statistics.stdev(window)
    downside_deviation = math.sqrt(
        statistics.fmean(min(excess_return, 0) ** 2 for excess_return in excess_returns)
    )
    sharpe = mean_excess / volatility * math.sqrt(TRADING_DAYS_PER_YEAR) if volatility else None
    sortino = (
        mean_excess / downside_deviation * math.sqrt(TRADING_DAYS_PER_YEAR)
        if downside_deviation
        else None
    )
    return sharpe, sortino


def _historical_cvar(returns: list[float], confidence: float = 0.95) -> float | None:
    window = returns[-TRADING_DAYS_PER_YEAR:]
    if len(window) < 20:
        return None
    tail_count = max(1, math.ceil(len(window) * (1 - confidence)))
    return statistics.fmean(sorted(window)[:tail_count]) * 100


def _rsi(prices: list[float], periods: int) -> float | None:
    if len(prices) <= periods:
        return None
    changes = [prices[index] - prices[index - 1] for index in range(1, len(prices))][-periods:]
    gains = statistics.fmean(max(change, 0) for change in changes)
    losses = statistics.fmean(max(-change, 0) for change in changes)
    if losses == 0:
        return 100.0
    relative_strength = gains / losses
    return 100 - (100 / (1 + relative_strength))


def _signal(return_60d: float | None, distance_sma20: float | None, rsi: float | None) -> str:
    if rsi is not None and rsi >= 70:
        return "extended"
    if rsi is not None and rsi <= 30:
        return "oversold"
    if return_60d is not None and distance_sma20 is not None:
        if return_60d > 0 and distance_sma20 > 0:
            return "positive trend"
        if return_60d < 0 and distance_sma20 < 0:
            return "negative trend"
    return "mixed"
