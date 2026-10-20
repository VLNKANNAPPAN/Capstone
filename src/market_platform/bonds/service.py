from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Literal

from market_platform.bonds.analytics import calculate_bond, interpolate_curve
from market_platform.bonds.models import (
    BondCalculation,
    BondCalculationRequest,
    BondLadderBucket,
    BondLadderProposal,
    BondLadderRequest,
    BondRefreshResult,
    BondRiskSummary,
    BondSecurity,
    BondUniverseSnapshot,
    YieldCurvePoint,
)
from market_platform.bonds.providers import PublicBondDataProvider

if TYPE_CHECKING:
    from market_platform.db.repository import SqlAlchemyDataRepository


class BondResearchService:
    def __init__(
        self,
        repository: SqlAlchemyDataRepository,
        *,
        provider: PublicBondDataProvider | None = None,
    ) -> None:
        self._repository = repository
        self._provider = provider

    def refresh(self) -> BondRefreshResult:
        provider = self._provider or PublicBondDataProvider()
        owns_provider = self._provider is None
        result = BondRefreshResult()
        curve: list[YieldCurvePoint] = []
        securities: list[BondSecurity] = []
        try:
            try:
                curve = provider.fetch_curve()
                result.curve_points = len(curve)
                result.source_date = curve[0].curve_date if curve else None
            except Exception as exc:  # public sources fail independently
                result.warnings.append(f"CCIL curve refresh failed: {str(exc)[:220]}")
            try:
                securities = provider.fetch_corporate_bonds()
                result.securities = len(securities)
            except Exception as exc:  # public sources fail independently
                result.warnings.append(f"Bond Central refresh failed: {str(exc)[:220]}")
            if not curve and not securities:
                raise RuntimeError("no public bond source returned usable data")
            self._repository.save_bond_data(securities=securities, curve=curve)
            return result
        finally:
            if owns_provider:
                provider.close()

    def snapshot(self) -> BondUniverseSnapshot:
        curve = self._repository.latest_yield_curve()
        securities = self._repository.list_bond_securities(limit=500)
        today = datetime.now(UTC).date()
        risk = [_risk_summary(security, curve, today) for security in securities]
        return BondUniverseSnapshot(
            generated_at=datetime.now(UTC),
            curve_date=curve[0].curve_date if curve else None,
            curve=curve,
            securities=securities,
            risk=risk,
            source_notes=[
                "CCIL publishes the sovereign zero-coupon curve; points are benchmarks, not "
                "executable quotes.",
                "Bond Central supplies reference terms. Database presence does not establish "
                "liquidity or suitability.",
                "No market price is inferred from coupon, face value or issue price.",
            ],
            methodology=(
                "Security terms and the latest sovereign curve retain source and availability "
                "timestamps. Corporate securities remain metadata-only until an actual trade or "
                "authorized valuation source is connected."
            ),
        )

    def calculate(self, request: BondCalculationRequest) -> BondCalculation:
        security = self._repository.get_bond_security(request.isin)
        if security is None:
            raise LookupError(f"unknown bond ISIN {request.isin}")
        return calculate_bond(
            security,
            clean_price=request.clean_price,
            settlement_date=request.settlement_date or datetime.now(UTC).date(),
        )

    def ladder(self, request: BondLadderRequest) -> BondLadderProposal:
        curve = self._repository.latest_yield_curve()
        if not curve:
            raise LookupError("yield curve is unavailable; refresh public bond data first")
        templates = {
            "low": [(0.5, 0.25), (1.0, 0.30), (3.0, 0.30), (5.0, 0.15)],
            "medium": [(1.0, 0.20), (3.0, 0.30), (5.0, 0.30), (10.0, 0.20)],
            "high": [(1.0, 0.10), (3.0, 0.20), (5.0, 0.30), (10.0, 0.25), (15.0, 0.15)],
        }
        allowed = [
            item
            for item in templates[request.risk_level]
            if item[0] <= request.horizon_years
        ]
        if not allowed:
            allowed = [(min(1.0, float(request.horizon_years)), 1.0)]
        total_weight = sum(weight for _, weight in allowed)
        buckets: list[BondLadderBucket] = []
        for tenor, raw_weight in allowed:
            allocation = raw_weight / total_weight
            yield_pct = interpolate_curve(curve, tenor)
            if yield_pct is None:
                continue
            buckets.append(
                BondLadderBucket(
                    label=_bucket_label(tenor),
                    tenor_years=tenor,
                    allocation_pct=round(allocation * 100, 2),
                    amount=round(request.budget * allocation, 2),
                    indicative_yield_pct=round(yield_pct, 4),
                    duration_proxy_years=round(tenor * 0.82, 3),
                )
            )
        weighted_yield = sum(
            item.indicative_yield_pct * item.allocation_pct / 100 for item in buckets
        )
        weighted_duration = sum(
            item.duration_proxy_years * item.allocation_pct / 100 for item in buckets
        )
        return BondLadderProposal(
            generated_at=datetime.now(UTC),
            budget=request.budget,
            horizon_years=request.horizon_years,
            risk_level=request.risk_level,
            curve_date=curve[0].curve_date,
            buckets=buckets,
            weighted_indicative_yield_pct=round(weighted_yield, 4),
            weighted_duration_proxy_years=round(weighted_duration, 3),
            warnings=[
                "This is a maturity-bucket model, not an executable list of securities.",
                "Indicative yields come from the sovereign curve and exclude tax, costs, "
                "reinvestment risk and credit spreads.",
                "Match actual coupon dates and liquidity with the investor's cash-flow needs "
                "before investing.",
            ],
            methodology=(
                "The budget is distributed across curve tenors no longer than the selected "
                "horizon. Risk level changes maturity concentration; it does not introduce "
                "unsupported return forecasts."
            ),
        )


def _risk_summary(
    security: BondSecurity,
    curve: list[YieldCurvePoint],
    today: date,
) -> BondRiskSummary:
    years = max((security.maturity_date - today).days / 365.25, 0)
    benchmark = interpolate_curve(curve, years)
    coupon_spread = (
        security.coupon_rate_pct - benchmark
        if security.coupon_rate_pct is not None and benchmark is not None
        else None
    )
    flags: list[str] = []
    if security.rating is None:
        flags.append("No current credit rating supplied by the selected record")
    if security.callable:
        flags.append("Callable: redemption timing may differ from stated maturity")
    if security.puttable:
        flags.append("Put option requires term-sheet review")
    if security.secured is False:
        flags.append("Unsecured obligation")
    flags.append("Current trading liquidity and executable price are not established")
    return BondRiskSummary(
        isin=security.isin,
        years_to_maturity=round(years, 3),
        annual_coupon_amount=(
            round(security.face_value * security.coupon_rate_pct / 100, 2)
            if security.coupon_rate_pct is not None
            else None
        ),
        benchmark_yield_pct=round(benchmark, 4) if benchmark is not None else None,
        coupon_minus_benchmark_pct=(round(coupon_spread, 4) if coupon_spread is not None else None),
        rating_band=_rating_band(security.rating),
        liquidity_status="metadata_only",
        risk_flags=flags,
    )


def _rating_band(
    rating: str | None,
) -> Literal["sovereign", "high", "medium", "low", "unrated"]:
    if not rating:
        return "unrated"
    normalized = rating.upper().replace(" ", "")
    if "SOVEREIGN" in normalized:
        return "sovereign"
    if normalized.startswith(("AAA", "AA+", "AA")):
        return "high"
    if normalized.startswith(("A", "BBB")):
        return "medium"
    return "low"


def _bucket_label(tenor: float) -> str:
    return f"{int(tenor * 12)}M sovereign bucket" if tenor < 1 else f"{tenor:g}Y sovereign bucket"


