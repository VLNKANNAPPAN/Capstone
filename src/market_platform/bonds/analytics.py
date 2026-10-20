from __future__ import annotations

import math
from datetime import date

from market_platform.bonds.models import (
    BondCalculation,
    BondRateScenario,
    BondSecurity,
    YieldCurvePoint,
)


def interpolate_curve(points: list[YieldCurvePoint], tenor_years: float) -> float | None:
    if not points:
        return None
    ordered = sorted(points, key=lambda item: item.tenor_years)
    if tenor_years <= ordered[0].tenor_years:
        return ordered[0].yield_pct
    if tenor_years >= ordered[-1].tenor_years:
        return ordered[-1].yield_pct
    for left, right in zip(ordered, ordered[1:], strict=False):
        if left.tenor_years <= tenor_years <= right.tenor_years:
            span = right.tenor_years - left.tenor_years
            weight = (tenor_years - left.tenor_years) / span
            return left.yield_pct + weight * (right.yield_pct - left.yield_pct)
    return None


def calculate_bond(
    security: BondSecurity,
    *,
    clean_price: float,
    settlement_date: date,
) -> BondCalculation:
    years = max((security.maturity_date - settlement_date).days / 365.25, 0)
    warnings = [
        "The calculation uses the entered clean price; it is not fetched as an executable quote.",
        "Coupon timing is approximated from payment frequency because the complete cash-flow "
        "calendar is not normalized yet.",
    ]
    if years <= 0:
        return BondCalculation(
            isin=security.isin,
            settlement_date=settlement_date,
            clean_price=clean_price,
            current_yield_pct=None,
            ytm_pct=None,
            macaulay_duration_years=None,
            modified_duration_years=None,
            convexity=None,
            dv01=None,
            scenarios=[],
            warnings=["The security has matured."],
            methodology="No analytics are produced after maturity.",
        )
    frequency = max(security.coupon_frequency, 1)
    coupon_rate = security.coupon_rate_pct or 0
    coupon = security.face_value * coupon_rate / 100 / frequency
    periods = max(1, math.ceil(years * frequency))
    cashflows = [coupon] * periods
    cashflows[-1] += security.face_value
    periodic_yield = _solve_periodic_yield(cashflows, clean_price)
    if periodic_yield is None:
        warnings.append("A stable yield-to-maturity solution could not be found for this price.")
        ytm_pct = None
        macaulay = None
        modified = None
        convexity = None
        dv01 = None
        scenarios: list[BondRateScenario] = []
    else:
        ytm_pct = periodic_yield * frequency * 100
        present_values = [
            cashflow / (1 + periodic_yield) ** period
            for period, cashflow in enumerate(cashflows, start=1)
        ]
        model_price = sum(present_values)
        macaulay = sum(
            (period / frequency) * pv
            for period, pv in enumerate(present_values, start=1)
        ) / model_price
        modified = macaulay / (1 + periodic_yield)
        convexity = sum(
            period * (period + 1) * pv
            for period, pv in enumerate(present_values, start=1)
        ) / (model_price * (1 + periodic_yield) ** 2 * frequency**2)
        dv01 = modified * clean_price * 0.0001
        scenarios = []
        for shift in (-100, -50, -25, 25, 50, 100):
            shifted_periodic = max(-0.99, periodic_yield + shift / 10_000 / frequency)
            shifted_price = _price(cashflows, shifted_periodic)
            scenarios.append(
                BondRateScenario(
                    shift_bps=shift,
                    repriced_clean_price=round(shifted_price, 4),
                    price_change_pct=round((shifted_price / clean_price - 1) * 100, 4),
                )
            )
    annual_coupon = security.face_value * coupon_rate / 100 if coupon_rate else None
    return BondCalculation(
        isin=security.isin,
        settlement_date=settlement_date,
        clean_price=clean_price,
        current_yield_pct=(annual_coupon / clean_price * 100 if annual_coupon else None),
        ytm_pct=ytm_pct,
        macaulay_duration_years=macaulay,
        modified_duration_years=modified,
        convexity=convexity,
        dv01=dv01,
        scenarios=scenarios,
        warnings=warnings,
        methodology=(
            "YTM is solved from the entered clean price and an approximate level-coupon schedule. "
            "Duration, convexity and DV01 use the same cash flows. Accrued interest, tax, "
            "settlement "
            "charges, calls, puts and default loss are excluded."
        ),
    )


def _solve_periodic_yield(cashflows: list[float], price: float) -> float | None:
    low = -0.95
    high = 1.0
    low_error = _price(cashflows, low) - price
    high_error = _price(cashflows, high) - price
    if low_error * high_error > 0:
        return None
    for _ in range(160):
        mid = (low + high) / 2
        error = _price(cashflows, mid) - price
        if abs(error) < 1e-10:
            return mid
        if low_error * error <= 0:
            high = mid
        else:
            low = mid
            low_error = error
    return (low + high) / 2


def _price(cashflows: list[float], periodic_yield: float) -> float:
    return sum(
        cashflow / (1 + periodic_yield) ** period
        for period, cashflow in enumerate(cashflows, start=1)
    )
