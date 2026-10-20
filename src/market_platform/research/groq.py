from __future__ import annotations

import json

import httpx

from market_platform.research.models import (
    ExplainResearchRequest,
    ResearchNarrativePayload,
    ResearchSnapshot,
)


class GroqResearchGenerator:
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "openai/gpt-oss-20b",
        base_url: str = "https://api.groq.com/openai/v1",
        timeout_seconds: float = 30,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model = model
        self._client = httpx.Client(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "CapstoneIndiaResearch/0.1",
            },
            timeout=timeout_seconds,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def generate(
        self,
        *,
        snapshot: ResearchSnapshot,
        request: ExplainResearchRequest,
    ) -> ResearchNarrativePayload:
        compact_snapshot = _compact_snapshot(snapshot)
        response = self._client.post(
            "/chat/completions",
            json={
                "model": self.model,
                "temperature": 0.2,
                "max_completion_tokens": 4096,
                "reasoning_effort": "low",
                "include_reasoning": False,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are the prototype synthesis layer for an Indian equity "
                            "research system. Use only the supplied structured evidence. "
                            "Never invent financial fundamentals, macro data, news, prices, "
                            "forecasts, or citations. Every evidence statement must reference "
                            "supplied evidence_ids. Explicitly state missing data. Explain in "
                            "beginner-friendly language. Do not issue buy, sell, target-price, "
                            "or personalized financial-advice instructions. Scenarios must be "
                            "conditional interpretations, not forecasts. Return every schema "
                            "field. Keep the executive summary under 70 words, other prose fields "
                            "under 55 words, each list to at most three concise items, and each "
                            "scenario to at most three assumptions."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "market": "India",
                                "horizon": request.horizon,
                                "risk_profile": request.risk_profile,
                                "research_snapshot": compact_snapshot,
                            },
                            separators=(",", ":"),
                        ),
                    },
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "india_equity_research_narrative",
                        "strict": True,
                        "schema": ResearchNarrativePayload.model_json_schema(),
                    },
                },
            },
        )
        response.raise_for_status()
        body = response.json()
        content = body["choices"][0]["message"]["content"]
        return ResearchNarrativePayload.model_validate(json.loads(content))


def _compact_snapshot(snapshot: ResearchSnapshot) -> dict[str, object]:
    """Keep free-tier prompts small while preserving an auditable evidence ledger."""
    priority_categories = {"technical", "risk", "liquidity", "fundamental"}
    retained = [item for item in snapshot.evidence if item.category in priority_categories]
    retained.extend([item for item in snapshot.evidence if item.category == "macro"][:4])
    for category in ("news_event", "video_event", "corporate_event"):
        retained.extend([item for item in snapshot.evidence if item.category == category][:2])
    evidence_ids = {item.evidence_id for item in retained}
    return {
        "symbol": snapshot.symbol,
        "company_name": snapshot.company_name,
        "exchange": snapshot.exchange,
        "currency": snapshot.currency,
        "cutoff": snapshot.cutoff.isoformat(),
        "technical": {
            "as_of": snapshot.technical.as_of.isoformat(),
            "observation_count": snapshot.technical.observation_count,
            "close": snapshot.technical.close,
            "signal": snapshot.technical.signal,
            "returns": snapshot.technical.returns.model_dump(mode="json"),
            "trend": {
                "distance_sma_20_pct": snapshot.technical.trend.distance_sma_20_pct,
                "distance_52_week_high_pct": (snapshot.technical.trend.distance_52_week_high_pct),
            },
            "momentum": {
                "rsi_14": snapshot.technical.momentum.rsi_14,
                "macd_histogram": snapshot.technical.momentum.macd_histogram,
            },
            "risk": snapshot.technical.risk.model_dump(mode="json"),
            "liquidity": snapshot.technical.liquidity.model_dump(mode="json"),
        },
        "coverage": snapshot.coverage.model_dump(mode="json"),
        "claims": [
            {
                **claim.model_dump(mode="json"),
                "evidence_ids": [
                    evidence_id for evidence_id in claim.evidence_ids if evidence_id in evidence_ids
                ],
            }
            for claim in snapshot.claims
        ],
        "evidence": [
            {
                "evidence_id": item.evidence_id,
                "category": item.category,
                "title": item.title[:180],
                "detail": item.detail[:320],
                "direction": item.direction,
                "source_type": item.source_type,
                "observed_at": item.observed_at.isoformat(),
                "freshness": item.freshness,
            }
            for item in retained
        ],
        "methodology": snapshot.methodology,
    }
