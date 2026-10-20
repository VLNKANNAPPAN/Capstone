from __future__ import annotations

from datetime import date, datetime

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from market_platform.analytics.models import MetricHistory, TechnicalSnapshot
from market_platform.analytics.technical import TechnicalAnalyticsService
from market_platform.bonds import (
    BondCalculation,
    BondCalculationRequest,
    BondLadderProposal,
    BondLadderRequest,
    BondRefreshResult,
    BondResearchService,
    BondUniverseSnapshot,
)
from market_platform.catalog import NseCompanyCatalogService
from market_platform.config import Settings
from market_platform.dashboard.models import AssetSummary, DashboardSnapshot, PriceSeries
from market_platform.dashboard.service import DashboardQueryService
from market_platform.data.providers.nse import NseSecurityMasterProvider
from market_platform.db.repository import SqlAlchemyDataRepository
from market_platform.domain.models import CorporateDisclosure, MacroObservation
from market_platform.fundamentals import (
    FilingIntelligenceService,
    FilingRefreshResult,
    FundamentalSnapshot,
)
from market_platform.portfolio import PortfolioProposal, PortfolioProposalService, PortfolioRequest
from market_platform.portfolio.groq import GroqPortfolioGenerator
from market_platform.research.groq import GroqResearchGenerator
from market_platform.research.models import (
    ExplainResearchRequest,
    ResearchNarrative,
    ResearchSnapshot,
    ThesisEvaluation,
    ThesisVersion,
)
from market_platform.research.on_demand import OnDemandResearchService
from market_platform.research.service import ResearchExplanationService, ResearchSnapshotService
from market_platform.research.thesis import ThesisEvaluationService, ThesisVersionService
from market_platform.youtube import DailyYouTubeDigest, YouTubeDigestService


def create_app(
    *,
    settings: Settings | None = None,
    repository: SqlAlchemyDataRepository | None = None,
    research_explainer: ResearchExplanationService | None = None,
    company_catalog: NseCompanyCatalogService | None = None,
    research_preparer: OnDemandResearchService | None = None,
    enable_on_demand: bool = False,
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    resolved_repository = repository or SqlAlchemyDataRepository(resolved_settings.database_url)
    dashboard = DashboardQueryService(resolved_repository)
    technical = TechnicalAnalyticsService(resolved_repository)
    research = ResearchSnapshotService(resolved_repository)
    theses = ThesisVersionService(resolved_repository)
    thesis_evaluations = ThesisEvaluationService(resolved_repository)
    filing_intelligence = FilingIntelligenceService(resolved_repository)
    bond_research = BondResearchService(resolved_repository)
    catalog = company_catalog or NseCompanyCatalogService(
        repository=resolved_repository,
        provider=NseSecurityMasterProvider(
            base_url=resolved_settings.nse_archive_base_url,
            timeout_seconds=resolved_settings.http_timeout_seconds,
            max_retries=resolved_settings.http_max_retries,
        ),
    )
    preparer = research_preparer
    if preparer is None and enable_on_demand:
        preparer = OnDemandResearchService(
            repository=resolved_repository,
            catalog=catalog,
            yahoo_base_url=resolved_settings.yahoo_data_base_url,
            google_news_base_url=resolved_settings.google_news_base_url,
            timeout_seconds=resolved_settings.http_timeout_seconds,
            max_retries=resolved_settings.http_max_retries,
        )
    youtube_digest = YouTubeDigestService(resolved_repository)
    portfolio_generator = (
        GroqPortfolioGenerator(
            api_key=resolved_settings.groq_api_key,
            model=resolved_settings.groq_model,
            base_url=resolved_settings.groq_api_base_url,
            timeout_seconds=resolved_settings.http_timeout_seconds,
        )
        if resolved_settings.groq_api_key
        else None
    )
    portfolio = PortfolioProposalService(
        repository=resolved_repository,
        generator=portfolio_generator,
    )
    explainer = research_explainer
    if explainer is None and resolved_settings.groq_api_key:
        explainer = ResearchExplanationService(
            repository=resolved_repository,
            generator=GroqResearchGenerator(
                api_key=resolved_settings.groq_api_key,
                model=resolved_settings.groq_model,
                base_url=resolved_settings.groq_api_base_url,
                timeout_seconds=resolved_settings.http_timeout_seconds,
            ),
        )

    application = FastAPI(
        title="Capstone Market Data API",
        version="0.2.0",
        description="Read-only observability API for acquisition and preprocessing.",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @application.get("/health")
    def health() -> dict[str, str]:
        try:
            with resolved_repository.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return {"status": "healthy", "database": "connected"}
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc

    @application.get("/api/v1/dashboard", response_model=DashboardSnapshot)
    def get_dashboard(
        limit: int = Query(default=12, ge=1, le=100),
    ) -> DashboardSnapshot:
        try:
            return dashboard.snapshot(limit=limit)
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc

    @application.get("/api/v1/assets/{symbol}/prices", response_model=PriceSeries)
    def get_prices(
        symbol: str,
        cutoff: datetime | None = None,
        timeframe: str | None = None,
        limit: int = Query(default=250, ge=1, le=5000),
    ) -> PriceSeries:
        try:
            return dashboard.price_series(
                symbol=symbol,
                cutoff=cutoff,
                timeframe=timeframe,
                limit=limit,
            )
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc

    @application.get("/api/v1/stocks", response_model=list[AssetSummary])
    def list_stocks() -> list[AssetSummary]:
        try:
            return [
                AssetSummary(
                    symbol=asset.symbol,
                    name=asset.name,
                    asset_type=asset.asset_type.value,
                    exchange=asset.exchange,
                    currency=asset.currency,
                    cik=asset.cik,
                    active=asset.active,
                )
                for asset in resolved_repository.list_assets()
            ]
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc

    @application.get("/api/v1/companies/search", response_model=list[AssetSummary])
    def search_companies(
        q: str = Query(min_length=1, max_length=100),
        limit: int = Query(default=10, ge=1, le=20),
    ) -> list[AssetSummary]:
        matches = catalog.search(q, limit=limit)
        return [
            AssetSummary(
                symbol=asset.symbol,
                name=asset.name,
                asset_type=asset.asset_type.value,
                exchange=asset.exchange,
                currency=asset.currency,
                cik=asset.cik,
                active=asset.active,
            )
            for asset in matches
        ]

    @application.get("/api/v1/stocks/{symbol}", response_model=AssetSummary)
    def get_stock(symbol: str) -> AssetSummary:
        try:
            asset = resolved_repository.get_asset(symbol)
            if asset is None:
                raise HTTPException(status_code=404, detail="stock not found")
            return AssetSummary(
                symbol=asset.symbol,
                name=asset.name,
                asset_type=asset.asset_type.value,
                exchange=asset.exchange,
                currency=asset.currency,
                cik=asset.cik,
                active=asset.active,
            )
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc

    @application.get("/api/v1/stocks/{symbol}/prices", response_model=PriceSeries)
    def get_stock_prices(
        symbol: str,
        cutoff: datetime | None = None,
        timeframe: str | None = None,
        limit: int = Query(default=250, ge=1, le=5000),
    ) -> PriceSeries:
        return get_prices(symbol=symbol, cutoff=cutoff, timeframe=timeframe, limit=limit)

    @application.get("/api/v1/stocks/{symbol}/technical", response_model=TechnicalSnapshot)
    def get_technical_snapshot(
        symbol: str,
        cutoff: datetime | None = None,
        timeframe: str = "1Day",
    ) -> TechnicalSnapshot:
        try:
            snapshot = technical.snapshot(symbol=symbol, cutoff=cutoff, timeframe=timeframe)
            if snapshot is None:
                raise HTTPException(status_code=404, detail="no price history found")
            return snapshot
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc

    @application.get(
        "/api/v1/stocks/{symbol}/disclosures",
        response_model=list[CorporateDisclosure],
    )
    def get_stock_disclosures(
        symbol: str,
        cutoff: datetime | None = None,
        limit: int = Query(default=50, ge=1, le=500),
    ) -> list[CorporateDisclosure]:
        try:
            point_in_time = cutoff or datetime.now().astimezone()
            return resolved_repository.list_disclosures_as_of(
                symbol=symbol,
                cutoff=point_in_time,
                limit=limit,
            )
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc

    @application.get(
        "/api/v1/stocks/{symbol}/metric-history",
        response_model=MetricHistory,
    )
    def get_metric_history(
        symbol: str,
        cutoff: datetime | None = None,
        window: int = Query(default=60, ge=60, le=252),
        step: int = Query(default=5, ge=1, le=21),
    ) -> MetricHistory:
        try:
            return technical.metric_history(
                symbol=symbol,
                cutoff=cutoff,
                window=window,
                step=step,
            )
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc

    @application.get(
        "/api/v1/stocks/{symbol}/fundamentals",
        response_model=FundamentalSnapshot,
    )
    def get_stock_fundamentals(
        symbol: str,
        cutoff: datetime | None = None,
        limit: int = Query(default=12, ge=1, le=40),
    ) -> FundamentalSnapshot:
        try:
            return filing_intelligence.snapshot(symbol=symbol, cutoff=cutoff, limit=limit)
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc

    @application.post(
        "/api/v1/stocks/{symbol}/fundamentals/refresh",
        response_model=FilingRefreshResult,
    )
    def refresh_stock_fundamentals(
        symbol: str,
        limit: int = Query(default=8, ge=1, le=20),
    ) -> FilingRefreshResult:
        try:
            return filing_intelligence.refresh(symbol=symbol, limit=limit)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"official filing acquisition failed: {str(exc)[:300]}",
            ) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc

    @application.get("/api/v1/macro", response_model=list[MacroObservation])
    def get_macro_observations(
        cutoff: datetime | None = None,
        latest_per_series: bool = True,
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> list[MacroObservation]:
        try:
            point_in_time = cutoff or datetime.now().astimezone()
            return resolved_repository.list_macro_as_of(
                cutoff=point_in_time,
                latest_per_series=latest_per_series,
                limit=limit,
            )
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc

    @application.get("/api/v1/bonds", response_model=BondUniverseSnapshot)
    def get_bond_universe() -> BondUniverseSnapshot:
        try:
            return bond_research.snapshot()
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc

    @application.post("/api/v1/bonds/refresh", response_model=BondRefreshResult)
    def refresh_bond_universe() -> BondRefreshResult:
        try:
            return bond_research.refresh()
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc

    @application.post("/api/v1/bonds/calculate", response_model=BondCalculation)
    def calculate_bond_metrics(request: BondCalculationRequest) -> BondCalculation:
        try:
            return bond_research.calculate(request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.post("/api/v1/bonds/ladder", response_model=BondLadderProposal)
    def propose_bond_ladder(request: BondLadderRequest) -> BondLadderProposal:
        try:
            return bond_research.ladder(request)
        except LookupError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @application.get("/api/v1/youtube/daily", response_model=DailyYouTubeDigest)
    def get_youtube_daily_digest(day: date | None = None) -> DailyYouTubeDigest:
        try:
            return youtube_digest.build(day=day)
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc

    @application.get("/api/v1/research/{symbol}", response_model=ResearchSnapshot)
    def get_research_snapshot(
        symbol: str,
        cutoff: datetime | None = None,
    ) -> ResearchSnapshot:
        try:
            snapshot = research.build(symbol=symbol, cutoff=cutoff)
            if snapshot is None:
                raise HTTPException(status_code=404, detail="research data not found")
            return snapshot
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc

    @application.post("/api/v1/research/{symbol}/prepare", response_model=ResearchSnapshot)
    def prepare_research_snapshot(
        symbol: str,
        refresh_news: bool = True,
    ) -> ResearchSnapshot:
        if preparer is None:
            snapshot = research.build(symbol=symbol)
            if snapshot is None:
                raise HTTPException(status_code=404, detail="research data not found")
            return snapshot
        try:
            return preparer.prepare(symbol=symbol, refresh_news=refresh_news)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"on-demand market data acquisition failed: {str(exc)[:300]}",
            ) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc

    @application.post("/api/v1/research/{symbol}/thesis", response_model=ThesisVersion)
    def create_thesis_version(
        symbol: str,
        cutoff: datetime | None = None,
    ) -> ThesisVersion:
        """Create an immutable thesis version at a historical or current cutoff."""
        try:
            thesis = theses.create(symbol=symbol, cutoff=cutoff)
            if thesis is None:
                raise HTTPException(
                    status_code=404,
                    detail="no point-in-time research data found at this cutoff",
                )
            return thesis
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc

    @application.get(
        "/api/v1/research/{symbol}/thesis/versions",
        response_model=list[ThesisVersion],
    )
    def list_thesis_versions(
        symbol: str,
        limit: int = Query(default=24, ge=1, le=120),
    ) -> list[ThesisVersion]:
        try:
            return theses.list(symbol=symbol, limit=limit)
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc

    @application.get(
        "/api/v1/theses/{thesis_id}/evaluation",
        response_model=ThesisEvaluation,
    )
    def evaluate_thesis(thesis_id: str) -> ThesisEvaluation:
        try:
            evaluation = thesis_evaluations.evaluate(thesis_id)
            if evaluation is None:
                raise HTTPException(status_code=404, detail="thesis evaluation data not found")
            return evaluation
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc

    @application.post("/api/v1/research/{symbol}/explain", response_model=ResearchNarrative)
    def explain_research(
        symbol: str,
        request: ExplainResearchRequest,
        cutoff: datetime | None = None,
    ) -> ResearchNarrative:
        if explainer is None:
            raise HTTPException(
                status_code=503,
                detail="Groq is not configured; set a rotated GROQ_API_KEY on the API server",
            )
        try:
            snapshot = (
                preparer.prepare(symbol=symbol, refresh_news=True)
                if preparer is not None and cutoff is None
                else research.build(symbol=symbol, cutoff=cutoff)
            )
            if snapshot is None:
                raise HTTPException(status_code=404, detail="research data not found")
            return explainer.explain(snapshot=snapshot, request=request)
        except httpx.HTTPStatusError as exc:
            provider_detail = "Groq rejected the synthesis request"
            try:
                payload = exc.response.json()
                error = payload.get("error") if isinstance(payload, dict) else None
                if isinstance(error, dict) and error.get("message"):
                    provider_detail = f"Groq rejected the synthesis request: {error['message']}"
            except (ValueError, TypeError):
                pass
            raise HTTPException(
                status_code=502,
                detail=provider_detail[:700],
            ) from exc
        except (httpx.RequestError, KeyError, ValueError) as exc:
            raise HTTPException(status_code=502, detail="Groq synthesis failed") from exc
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc

    @application.post("/api/v1/portfolio/propose", response_model=PortfolioProposal)
    def propose_portfolio(request: PortfolioRequest) -> PortfolioProposal:
        try:
            return portfolio.propose(request)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc

    return application


app = create_app(enable_on_demand=True)


def run() -> None:
    uvicorn.run("market_platform.api.app:app", host="127.0.0.1", port=8000, reload=True)
