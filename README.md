# Capstone Market Research Platform

This repository begins with the data foundation for a leakage-aware financial research
platform. The current scope is intentionally limited to acquisition, normalization,
quality control, point-in-time storage, and retrieval.

## Current capabilities

- Vendor-neutral provider contracts
- Alpaca historical bar acquisition
- SEC submissions acquisition for 10-K, 10-Q, and 8-K filings
- Raw payload retention and canonical PostgreSQL tables
- UTC timestamp normalization and point-in-time cutoffs
- Idempotent ingestion, watermarks, run records, and data-quality issues
- SQLite-compatible tests and PostgreSQL development environment
- FastAPI data-observability endpoints
- React dashboard with live polling, price visualization, ingestion history, and quality status
- Twenty-stock Indian large-cap research bootstrap and transparent technical/risk metrics
- Full NSE main-board and SME symbol search from the official security-master catalog
- On-demand company registration, historical-price acquisition, and recent Google News refresh
- Normalized news/social content schema and a no-key GDELT news connector
- Conservative Indian-company entity linking and metadata-only Google News RSS fallback
- NSE/BSE corporate announcement and financial-result normalization
- Official NSE XBRL financial-result acquisition with document checksums and revision history
- Deterministic Indian filing facts, derived margins, point-in-time provenance, and research evidence IDs
- RBI CPI, real-GDP, call-money, and current policy-rate ingestion
- Point-in-time stock catalog and deterministic technical analytics API
- Evidence-grounded research snapshots and an auditable single-model Groq prototype
- YouTube Data API ingestion and IST daily digests for five Indian finance channels
- Indian fixed-income research desk with the official CCIL sovereign zero-coupon curve,
  SEBI-backed Bond Central security terms, price-to-YTM analytics, duration/DV01 shocks,
  and a deterministic maturity-ladder planner

Multi-agent orchestration and trade execution remain outside the current increment. Portfolio
and bond outputs are deterministic research aids; they are not orders or personalized advice.

## Local setup

```powershell
Copy-Item .env.example .env
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
docker compose up -d postgres
alembic upgrade head
```

Set a real contact address in `SEC_USER_AGENT` before calling SEC APIs. Add Alpaca keys
only when using the Alpaca adapter.

For the optional prototype explanation endpoint, set a newly rotated `GROQ_API_KEY` only in
the API process environment. The key is never sent to the browser. The default model is
`openai/gpt-oss-20b` and can be changed with `GROQ_MODEL`.

## Commands

```powershell
capstone-data init-db
capstone-data register-asset --symbol AAPL --cik 0000320193 --name "Apple Inc."
capstone-data ingest-sec --symbol AAPL --cik 0000320193
capstone-data ingest-market --symbol AAPL --start 2026-01-01T00:00:00Z --end 2026-02-01T00:00:00Z --timeframe 1Day
capstone-data show-bars --symbol AAPL --as-of 2026-02-01T00:00:00Z
capstone-data seed-india-research
capstone-data ingest-nse-bhavcopy --date 2026-09-25
capstone-data ingest-news --provider google --symbol RELIANCE.NS --query '"Reliance Industries"'
capstone-data ingest-disclosures --symbol RELIANCE.NS --from 2026-09-01 --to 2026-09-26 --exchange both
capstone-data ingest-rbi --history-limit 24
capstone-data ingest-youtube --lookback-hours 48 --max-per-channel 10
capstone-data ingest-bonds
```

The research page does not download history for every NSE symbol. It searches lightweight
security-master metadata, then acquires and stores price history only when a user selects an
uncached company. Recent company-linked Google News metadata is refreshed before the AI brief.

### Point-in-time thesis lifecycle

The Research page includes the first no-agent ThesisGraph experiments:

- replay a company using only records available at a chosen historical cutoff;
- persist immutable, idempotent thesis versions;
- compare each version with the previous historical version using declared materiality thresholds;
- evaluate deterministic technical and risk thesis breakers; and
- report evidence coverage separately from forecast confidence.
- detect declared price/news, horizon and return/risk contradictions;
- run leave-one-evidence-category-out confidence sensitivity checks; and
- evaluate saved theses on later 5, 20 and 60-trading-day returns without leaking those
  outcomes into thesis creation.

Use `POST /api/v1/research/{symbol}/thesis?cutoff=<ISO-8601>` to save a replay and
`GET /api/v1/research/{symbol}/thesis/versions` to retrieve its audit timeline. These endpoints
do not call Groq and therefore use no LLM quota.

### Indian filing intelligence

The Evidence page can acquire supported NSE financial-result XBRL documents on demand. The
backend stores the original document, checksum, filing revision, period, consolidated/standalone
basis, audit status, source concept and `available_at` timestamp. Direct statement facts and
formula-derived metrics are labeled separately. Missing balance-sheet or cash-flow concepts stay
missing rather than being estimated by an LLM.

```text
GET  /api/v1/stocks/{symbol}/fundamentals
POST /api/v1/stocks/{symbol}/fundamentals/refresh?limit=8
```

Parsed filing facts are also included as `exchange_xbrl_fact` evidence in the deterministic
research snapshot and therefore become inspectable inputs to thesis versions and optional Groq
explanations.

Use `GET /api/v1/theses/{thesis_id}/evaluation` for the separate forward-outcome audit. A
constructive thesis is scored against positive returns, cautious/at-risk against negative returns,
and neutral theses remain unscored. The evaluation result is diagnostic rather than investment
advice or a claim of causal attribution.

Set `YOUTUBE_API_KEY` only in the backend process environment. YouTube summaries use
titles, shortened descriptions, and public statistics; video audio and transcripts are
not analyzed.

### Indian bond research

The Bonds page separates three concepts that should not be mixed:

- CCIL's published zero-coupon curve is a sovereign term-structure benchmark;
- Bond Central records are corporate-bond reference terms, not proof of a current executable
  price or liquidity; and
- YTM, duration, convexity, DV01, and rate shocks are calculated only after the user supplies a
  clean price.

```text
GET  /api/v1/bonds
POST /api/v1/bonds/refresh
POST /api/v1/bonds/calculate
POST /api/v1/bonds/ladder
```

The ladder is a transparent maturity-bucket model based on the sovereign curve. It does not
select an executable bond, estimate default probability, include tax, or replace review of the
offer document and current rating. The Learn page includes yield, duration, spread, and ladder
lessons with scenario plots.

Run tests with `pytest`.

## Data dashboard

Start the API:

```powershell
.venv\Scripts\Activate.ps1
capstone-api
```

In another terminal, start the React application:

```powershell
cd apps\web
pnpm install
pnpm dev
```

Open `http://127.0.0.1:5173`. The dashboard polls the API every five seconds and displays
only records stored by the acquisition pipeline. It does not generate sample financial
values when the database is empty.

See [docs/project-phases.md](docs/project-phases.md) for the staged Option A to Option C
plan and [docs/content-data-sources.md](docs/content-data-sources.md) for the news and
social acquisition policy.

The India-specific backend sequence, source policy, endpoint list, and credential gates are
documented in [docs/india-backend-roadmap.md](docs/india-backend-roadmap.md).

The `yahoo_research` historical bootstrap is for a private academic prototype only. It is
not the production Indian market-data source and should be replaced with a licensed or
broker-authorized feed before deployment or redistribution.
