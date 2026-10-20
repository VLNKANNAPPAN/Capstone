# Project Phases: Option A Baseline to Option C Attribution

## Architectural position

Option A is the correct baseline because it provides a complete, understandable decision
pipeline. Option C should then replace selected coarse analyst stages with fine-grained,
numerically aggregated evidence units. This creates a fair comparison because the data,
risk, portfolio, and evaluation infrastructure remain fixed.

The Option A proposal names twelve roles despite describing ten agents. The implementation
should also distinguish agents from software components:

- Data access is this provider and repository layer, not an LLM agent.
- Risk metrics and position constraints are deterministic code.
- Output formatting is an API responsibility, not an agent.
- Intent parsing should begin as validated request schemas and only use an LLM when natural
  language adds demonstrated value.

This produces a smaller and more defensible initial agent system.

## Phase 1: Point-in-time data foundation

Status: complete for generic market bars, content, and legacy SEC filing metadata. SEC is
retained only as a provider example; it is not the fundamentals path for the Indian product.

- Provider contracts, normalization, raw revisions, canonical storage
- Availability timestamps, idempotency, quality quarantine, watermarks
- PostgreSQL and migrations

## Phase 2: Data observability dashboard

Status: implemented in this checkpoint.

- Read-only FastAPI endpoints
- Dataset counts and freshness
- Price series visualization
- Ingestion-run audit trail
- Source status, SEC filing list, and quality queue
- Five-second polling for newly committed data

## Phase 3: India-first acquisition completeness

- Replace the research-only Yahoo bootstrap with official NSE CM-UDiFF bhavcopy ingestion
- Version the NSE security master, symbol changes, and corporate actions
- Add authorized Indian financial results and corporate-announcement ingestion
- Add RBI macro releases and a broker-authorized WebSocket only after EOD ingestion is stable
- Produce completeness, duplicates, gaps, and freshness reports

## Phase 4: Deterministic preprocessing

- Corporate-action handling and adjusted-price policy
- Returns, rolling volatility, liquidity, and missing-session detection
- Filing text extraction, sectioning, and provenance
- News deduplication and entity linking
- Versioned feature definitions and preprocessing runs

## Phase 5: Option A baseline

- Technical, reports, news, and sentiment analyst contracts
- Coordinator and equity-manager orchestration
- Debate disabled by default, then added as a measured toggle
- Deterministic risk gate and portfolio optimizer
- Full trace, evidence, cost, and latency capture

## Phase 6: Leakage-safe evaluation

- Deterministic baselines before LLM experiments
- Decision-time and execution-time separation
- Transaction costs and walk-forward evaluation
- Option A with no debate, conditional debate, and always debate

## Phase 7: Option C retrofit

Start with two decompositions instead of all proposed sub-agents:

1. Reports becomes Profitability, Valuation, and Growth evidence units.
2. Market analysis becomes Trend and Volatility evidence units.

Use a deterministic weighted aggregation layer. Log each contribution at decision time,
but do not call it causal attribution. Compare logged weights with leave-one-component-out
backtests to measure interaction effects and validate or reject the approximation.

## Phase 8: Option C expansion

- Split news events from news sentiment
- Add per-regime calibration
- Add constrained weight updates from resolved outcomes
- Compare Option A and Option C on performance, calibration, cost, and latency
