from __future__ import annotations

import hashlib
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

import httpx

from market_platform.fundamentals.models import ParsedFiling, ParsedFilingFact

PARSER_VERSION = "indian-xbrl-v1"
XBRL_INSTANCE_NS = "http://www.xbrl.org/2003/instance"

CONCEPT_MAP: dict[str, str] = {
    "RevenueFromOperations": "revenue",
    "InterestEarned": "revenue",
    "TotalIncome": "total_income",
    "Income": "total_income",
    "OtherIncome": "other_income",
    "FinanceCosts": "finance_costs",
    "DepreciationDepletionAndAmortisationExpense": "depreciation_amortization",
    "ProfitBeforeExceptionalItemsAndTax": "profit_before_exceptional_and_tax",
    "ProfitBeforeTax": "profit_before_tax",
    "ProfitLossForPeriod": "net_profit",
    "NetProfitLossForThePeriod": "net_profit",
    "ProfitOrLossAttributableToOwnersOfParent": "net_profit_parent",
    "TaxExpense": "tax_expense",
    "ExceptionalItemsBeforeTax": "exceptional_items",
    "EmployeeBenefitExpense": "employee_expense",
    "Expenses": "total_expenses",
    "PaidUpValueOfEquityShareCapital": "equity_share_capital",
    "BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations": "basic_eps",
    "BasicEarningsLossPerShareFromContinuingOperations": "basic_eps",
    "DilutedEarningsLossPerShareFromContinuingAndDiscontinuedOperations": "diluted_eps",
    "DilutedEarningsLossPerShareFromContinuingOperations": "diluted_eps",
    "DeclarationOfUnmodifiedOpinionOrStatementOnImpactOfAuditQualification": (
        "audit_qualification_status"
    ),
    "DisclosureOfNotesOnFinancialResultsExplanatoryTextBlock": "filing_notes",
}


@dataclass(frozen=True, slots=True)
class ContextPeriod:
    start: str | None
    end: str | None
    instant: str | None
    has_dimensions: bool


class XbrlDocumentClient:
    def __init__(
        self,
        *,
        timeout_seconds: float = 30,
        max_retries: int = 3,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = httpx.Client(
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; MarketLabAcademic/1.0)",
                "Accept": "application/xml,text/xml,*/*",
            },
            timeout=timeout_seconds,
            transport=transport,
            follow_redirects=True,
        )
        self._max_retries = max_retries
        self._sleep = sleep

    def close(self) -> None:
        self._client.close()

    def download(self, url: str) -> tuple[str, str, str]:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.get(url)
                if response.status_code in {429, 500, 502, 503, 504}:
                    raise httpx.HTTPStatusError(
                        "retryable filing response",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                text = response.text
                if "<xbrli:xbrl" not in text and "<xbrl" not in text:
                    raise ValueError("document is not an XBRL instance")
                checksum = hashlib.sha256(response.content).hexdigest()
                content_type = response.headers.get("Content-Type", "application/xml").split(";")[0]
                return text, checksum, content_type
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt < self._max_retries:
                    self._sleep(min(0.75 * (2**attempt), 6))
        raise RuntimeError("filing document download failed after retries") from last_error


def parse_xbrl(xml_text: str, *, expected_period_end: str | None = None) -> ParsedFiling:
    root = ET.fromstring(xml_text)
    taxonomy = "unknown"
    for element in root:
        if _local_name(element.tag) == "schemaRef":
            taxonomy = next(
                (value for key, value in element.attrib.items() if _local_name(key) == "href"),
                "unknown",
            )
            break
    contexts = _contexts(root)
    metadata = _text_metadata(root)
    target_end = _normalize_date(expected_period_end) or metadata.get("DateOfEndOfReportingPeriod")
    candidates: dict[str, tuple[int, ParsedFilingFact]] = {}
    for element in root:
        context_id = element.attrib.get("contextRef")
        source_concept = _local_name(element.tag)
        normalized_metric = CONCEPT_MAP.get(source_concept)
        if not context_id or normalized_metric is None or context_id not in contexts:
            continue
        context = contexts[context_id]
        if context.has_dimensions:
            continue
        score = _context_score(context_id, context, target_end)
        text_value = (element.text or "").strip()
        numeric = _decimal_or_none(text_value) if element.attrib.get("unitRef") else None
        fact = ParsedFilingFact(
            normalized_metric=normalized_metric,
            source_concept=source_concept,
            context_id=context_id,
            period_start=context.start,
            period_end=context.end,
            instant=context.instant,
            value_numeric=numeric,
            value_text=None if numeric is not None else text_value or None,
            unit=element.attrib.get("unitRef"),
            decimals=element.attrib.get("decimals"),
        )
        previous = candidates.get(normalized_metric)
        if previous is None or score > previous[0]:
            candidates[normalized_metric] = (score, fact)
    facts = [item[1] for item in candidates.values()]
    facts.extend(_derived_facts(facts, target_end))
    basis_text = metadata.get("NatureOfReportStandaloneConsolidated", "").casefold()
    basis: Literal["consolidated", "standalone", "unknown"] = (
        "consolidated"
        if "consolidated" in basis_text and "non-consolidated" not in basis_text
        else "standalone" if basis_text else "unknown"
    )
    audited_text = metadata.get("WhetherResultsAreAuditedOrUnaudited", "").casefold()
    audited = None if not audited_text else "unaudited" not in audited_text
    chosen_period = next(
        (context for context in contexts.values() if context.end == target_end), None
    )
    return ParsedFiling(
        parser_version=PARSER_VERSION,
        taxonomy=taxonomy,
        basis=basis,
        audited=audited,
        reporting_quarter=metadata.get("ReportingQuarter"),
        period_start=chosen_period.start if chosen_period else None,
        period_end=target_end,
        facts=sorted(facts, key=lambda item: (item.derived, item.normalized_metric)),
    )


def _contexts(root: ET.Element) -> dict[str, ContextPeriod]:
    values: dict[str, ContextPeriod] = {}
    namespace = {"xbrli": XBRL_INSTANCE_NS}
    for context in root.findall("xbrli:context", namespace):
        context_id = context.attrib.get("id")
        if not context_id:
            continue
        period = context.find("xbrli:period", namespace)
        if period is None:
            continue
        values[context_id] = ContextPeriod(
            start=_child_text(period, f"{{{XBRL_INSTANCE_NS}}}startDate"),
            end=_child_text(period, f"{{{XBRL_INSTANCE_NS}}}endDate"),
            instant=_child_text(period, f"{{{XBRL_INSTANCE_NS}}}instant"),
            has_dimensions=context.find("xbrli:scenario", namespace) is not None,
        )
    return values


def _text_metadata(root: ET.Element) -> dict[str, str]:
    wanted = {
        "DateOfEndOfReportingPeriod",
        "NatureOfReportStandaloneConsolidated",
        "WhetherResultsAreAuditedOrUnaudited",
        "ReportingQuarter",
    }
    return {
        _local_name(element.tag): (element.text or "").strip()
        for element in root
        if _local_name(element.tag) in wanted and (element.text or "").strip()
    }


def _derived_facts(facts: list[ParsedFilingFact], period_end: str | None) -> list[ParsedFilingFact]:
    values = {
        fact.normalized_metric: fact.value_numeric
        for fact in facts
        if fact.value_numeric is not None
    }
    context_id = "derived"
    derived: list[ParsedFilingFact] = []

    def add(metric: str, value: Decimal | None, unit: str, formula: str) -> None:
        if value is None:
            return
        derived.append(
            ParsedFilingFact(
                normalized_metric=metric,
                source_concept="derived",
                context_id=context_id,
                period_end=period_end,
                value_numeric=value,
                unit=unit,
                derived=True,
                formula=formula,
            )
        )

    revenue = values.get("revenue") or values.get("total_income")
    pbeit = values.get("profit_before_exceptional_and_tax")
    finance = values.get("finance_costs")
    depreciation = values.get("depreciation_amortization")
    net_profit = values.get("net_profit_parent") or values.get("net_profit")
    pbt = values.get("profit_before_tax")
    tax = values.get("tax_expense")
    ebit = pbeit + finance if pbeit is not None and finance is not None else None
    ebitda = ebit + depreciation if ebit is not None and depreciation is not None else None
    add("ebit", ebit, "INR", "profit_before_exceptional_and_tax + finance_costs")
    add("ebitda", ebitda, "INR", "ebit + depreciation_amortization")
    add("operating_margin_pct", _ratio(ebit, revenue), "percent", "ebit / revenue * 100")
    add("ebitda_margin_pct", _ratio(ebitda, revenue), "percent", "ebitda / revenue * 100")
    add("net_margin_pct", _ratio(net_profit, revenue), "percent", "net_profit / revenue * 100")
    add(
        "effective_tax_rate_pct",
        _ratio(tax, pbt),
        "percent",
        "tax_expense / profit_before_tax * 100",
    )
    add(
        "interest_coverage",
        _ratio(ebit, finance, percentage=False),
        "ratio",
        "ebit / finance_costs",
    )
    return derived


def _ratio(
    numerator: Decimal | None,
    denominator: Decimal | None,
    *,
    percentage: bool = True,
) -> Decimal | None:
    if numerator is None or denominator is None or denominator == Decimal(0):
        return None
    result = numerator / denominator
    return result * 100 if percentage else result


def _context_score(context_id: str, context: ContextPeriod, target_end: str | None) -> int:
    score = 0
    if target_end and (context.end == target_end or context.instant == target_end):
        score += 10
    if context_id.startswith("One"):
        score += 5
    if context.instant:
        score += 1
    return score


def _normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    stripped = value.strip()
    for fmt in ("%Y-%m-%d", "%d-%b-%Y"):
        try:
            from datetime import datetime

            return datetime.strptime(stripped, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _decimal_or_none(value: str) -> Decimal | None:
    try:
        return Decimal(value.replace(",", ""))
    except InvalidOperation:
        return None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_text(parent: ET.Element, tag: str) -> str | None:
    child = parent.find(tag)
    return child.text.strip() if child is not None and child.text else None
