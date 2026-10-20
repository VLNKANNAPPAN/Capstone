from __future__ import annotations

import json

import httpx

from market_platform.portfolio.models import (
    PortfolioHolding,
    PortfolioNarrative,
    PortfolioRequest,
)


class GroqPortfolioGenerator:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float,
    ) -> None:
        self.model = model
        self._client = httpx.Client(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout_seconds,
        )

    def close(self) -> None:
        self._client.close()

    def generate(
        self,
        *,
        request: PortfolioRequest,
        holdings: list[PortfolioHolding],
    ) -> PortfolioNarrative:
        compact = [
            {
                "symbol": item.symbol,
                "sector": item.sector,
                "weight_pct": round(item.weight_pct, 2),
                "signal": item.signal,
                "sharpe": item.sharpe,
                "sortino": item.sortino,
                "volatility_pct": item.volatility_pct,
                "maximum_drawdown_pct": item.maximum_drawdown_pct,
                "return_60d_pct": item.return_60d_pct,
                "news_headlines": item.news_headlines[:2],
            }
            for item in holdings
        ]
        sectors = sorted({item.sector for item in holdings})
        response = self._client.post(
            "/chat/completions",
            json={
                "model": self.model,
                "temperature": 0.1,
                "max_completion_tokens": 1800,
                "reasoning_effort": "low",
                "include_reasoning": False,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Explain an educational Indian-equity model portfolio. Use only the "
                            "supplied deterministic allocation and evidence. Do not change "
                            "weights, promise returns, give target prices, or call an asset a "
                            "guaranteed buy. Do not invent liquidity claims, stop-losses, numeric "
                            "thresholds, sector counts, or rebalancing rules. State no fact that "
                            "is absent from the payload. Keep every list to at most three concise "
                            "items and return every field."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "budget": request.budget,
                                "risk_level": request.risk_level,
                                "duration_months": request.duration_months,
                                "sector_count": len(sectors),
                                "sectors": sectors,
                                "holdings": compact,
                            },
                            separators=(",", ":"),
                        ),
                    },
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "educational_portfolio_narrative",
                        "strict": True,
                        "schema": PortfolioNarrative.model_json_schema(),
                    },
                },
            },
        )
        response.raise_for_status()
        return PortfolioNarrative.model_validate_json(
            response.json()["choices"][0]["message"]["content"]
        )
