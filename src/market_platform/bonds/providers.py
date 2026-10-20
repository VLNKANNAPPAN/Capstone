from __future__ import annotations

import io
import re
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import quote

import httpx
import msoffcrypto  # type: ignore[import-untyped]
import xlrd  # type: ignore[import-untyped]

from market_platform.bonds.models import BondSecurity, YieldCurvePoint

CCIL_ANALYTICS_URL = "https://www.ccilindia.com/analytics"
BOND_CENTRAL_API = "https://api.bondcentral.in"
BOND_CENTRAL_URL = "https://bondcentral.in"
PUBLIC_ISSUERS = (
    "STATE BANK OF INDIA",
    "HDFC BANK LIMITED",
    "NATIONAL HIGHWAYS AUTHORITY OF INDIA",
    "REC LIMITED",
    "POWER FINANCE CORPORATION LIMITED",
)


class PublicBondDataProvider:
    def __init__(
        self,
        *,
        timeout_seconds: float = 30,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; MarketLabAcademic/1.0)",
                "Accept": "application/json,text/html,application/vnd.ms-excel,*/*",
            },
            timeout=timeout_seconds,
            transport=transport,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def fetch_curve(self) -> list[YieldCurvePoint]:
        page = self._client.get(CCIL_ANALYTICS_URL)
        page.raise_for_status()
        match = re.search(
            r'data-url="([^"]*Tenor Wise Zero Coupon Yield-'
            r'([0-9]{4}-[0-9]{2}-[0-9]{2})_[^"]+\.xls)"',
            page.text,
        )
        if match is None:
            raise RuntimeError("CCIL did not publish a discoverable tenor-wise yield workbook")
        source_url = match.group(1)
        curve_date = date.fromisoformat(match.group(2))
        response = self._client.get(source_url)
        response.raise_for_status()
        workbook = _open_public_workbook(response.content)
        sheet = workbook.sheet_by_index(0)
        available_at = datetime.combine(curve_date, datetime.max.time(), tzinfo=UTC)
        points: list[YieldCurvePoint] = []
        for row in range(11, sheet.nrows):
            tenor = _number(sheet.cell_value(row, 0))
            yield_pct = _number(sheet.cell_value(row, 1))
            if tenor is None or yield_pct is None:
                continue
            if tenor <= 0 or yield_pct <= 0:
                continue
            points.append(
                YieldCurvePoint(
                    curve_date=curve_date,
                    tenor_years=tenor,
                    yield_pct=yield_pct,
                    source="ccil_zcyc",
                    source_url=source_url,
                    available_at=available_at,
                )
            )
        if len(points) < 10:
            raise RuntimeError("CCIL yield workbook did not contain a usable curve")
        return points

    def fetch_corporate_bonds(self, *, per_issuer: int = 4) -> list[BondSecurity]:
        today = datetime.now(UTC).date()
        available_at = datetime.now(UTC)
        selected: list[BondSecurity] = []
        for issuer in PUBLIC_ISSUERS:
            try:
                response = self._client.get(
                    f"{BOND_CENTRAL_API}/securities/",
                    params={"issuer": issuer, "page": 1, "size": 100},
                    headers={"Origin": BOND_CENTRAL_URL},
                )
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError):
                # The public endpoint occasionally fails for one issuer. Preserve any
                # independently retrieved issuers instead of discarding the entire refresh.
                continue
            records = payload.get("data", []) if isinstance(payload, dict) else []
            candidates: list[BondSecurity] = []
            for wrapper in records:
                if not isinstance(wrapper, dict) or not isinstance(wrapper.get("data"), dict):
                    continue
                security = _bond_security(wrapper["data"], available_at)
                if security is None or security.maturity_date <= today:
                    continue
                candidates.append(security)
            candidates.sort(key=lambda item: (item.maturity_date, -(item.coupon_rate_pct or 0)))
            if not candidates:
                continue
            step = max(1, len(candidates) // max(per_issuer, 1))
            sampled = candidates[::step][:per_issuer]
            selected.extend(sampled)
        unique = {item.isin: item for item in selected}
        return sorted(unique.values(), key=lambda item: (item.issuer, item.maturity_date))


def _open_public_workbook(content: bytes) -> xlrd.book.Book:
    try:
        return xlrd.open_workbook(file_contents=content)
    except xlrd.XLRDError as exc:
        if "encrypted" not in str(exc).casefold():
            raise
    encrypted = io.BytesIO(content)
    decrypted = io.BytesIO()
    office_file = msoffcrypto.OfficeFile(encrypted)
    office_file.load_key(password="VelvetSweatshop")
    office_file.decrypt(decrypted)
    return xlrd.open_workbook(file_contents=decrypted.getvalue())


def _bond_security(data: dict[str, Any], available_at: datetime) -> BondSecurity | None:
    isin = str(data.get("isin") or "").strip().upper()
    issuer = str(data.get("issuer") or "").strip()
    maturity = _date(data.get("maturity_date"))
    face_value = _number(data.get("face_value"))
    coupon = _number(data.get("coupon_rate"))
    status = str(data.get("security_status") or "ACTIVE").strip().upper()
    if not isin or not issuer or maturity is None or face_value is None or face_value <= 0:
        return None
    if status not in {"ACTIVE", "LIVE", "LISTED"}:
        return None
    if maturity.year >= 9990:
        # Bond Central represents perpetual instruments with a 9999 maturity sentinel.
        # They require call-date/perpetuity analytics, so do not treat them as fixed-term bonds.
        return None
    interest_type = str(data.get("interest_type") or "")
    if coupon is None or coupon <= 0 or (interest_type and "fixed" not in interest_type.casefold()):
        return None
    ratings_value = data.get("ratings")
    ratings: list[Any] = ratings_value if isinstance(ratings_value, list) else []
    rating_record = next(
        (item for item in ratings if isinstance(item, dict) and item.get("cra_rating")),
        {},
    )
    secured_value = str(data.get("secured_unsecured") or "").casefold()
    issue_date = _date(data.get("allotment_date"))
    issue_price = _number(data.get("issue_price"))
    return BondSecurity(
        isin=isin,
        issuer=issuer,
        security_name=str(data.get("security_name") or data.get("isin_description") or isin),
        coupon_rate_pct=coupon,
        coupon_frequency=_frequency(str(data.get("frequency") or "")),
        issue_date=issue_date,
        maturity_date=maturity,
        face_value=face_value,
        issue_price=issue_price,
        rating=_clean(rating_record.get("cra_rating")),
        rating_agency=_clean(rating_record.get("credit_rating_agency_name")),
        rating_outlook=_clean(rating_record.get("ratings_outlook")),
        secured=(
            True
            if secured_value == "secured"
            else False if "unsecured" in secured_value else None
        ),
        seniority=_clean(data.get("seniority")),
        callable=bool(_clean(data.get("call_description"))),
        puttable=bool(_clean(data.get("put_description"))),
        sector=_clean(data.get("business_sector")),
        status=status,
        source="bond_central",
        source_url=f"{BOND_CENTRAL_URL}/details?isin={quote(isin)}",
        available_at=available_at,
    )


def _frequency(value: str) -> int:
    normalized = value.casefold()
    if "month" in normalized:
        return 12
    if "quarter" in normalized:
        return 4
    if "half" in normalized or "semi" in normalized or "twice" in normalized:
        return 2
    return 1


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    missing = {"not applicable", "none", "null", "nan"}
    return None if not text or text.casefold() in missing else text


def _number(value: object) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _date(value: object) -> date | None:
    if value is None:
        return None
    text = str(value).strip().split(" ", 1)[0]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None
