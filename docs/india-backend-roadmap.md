# India-First Backend Roadmap

## Product boundary

The dashboard is an administrator and verification surface. It reads normalized records,
feature outputs, run history, freshness, and quality failures. It is not the data source and
does not calculate decision evidence in the browser.

The backend remains a modular monolith with separate acquisition workers. Deterministic
services acquire, normalize, validate, store, and calculate features. Later Option A agents
may consume only versioned backend snapshots; they must not call vendors directly.

## Source and credential sequence

| Stage | Data | Initial source | Credential required | Production position |
| --- | --- | --- | --- | --- |
| Current | Daily history for 20-stock prototype | Yahoo chart adapter | No | Research bootstrap only; no redistribution |
| Current | News discovery | GDELT plus Google News RSS development fallback | No | Metadata only; Google feed is personal/non-commercial |
| Current | Exchange disclosures/results | NSE and BSE public website data used by their filing pages | No | Academic prototype; verify exchange terms before deployment |
| Current | Macro and rates | RBI DBIE mirror from RBI Innovation Hub plus official RBI current-rates page | No | Store first-observed availability and source vintage |
| Current | Selected finance videos | YouTube Data API v3 uploads playlists | Google API key | Metadata digest; no transcript claim |
| Current | Sovereign term structure | CCIL tenor-wise zero-coupon yield curve | No API key | Benchmark curve; not executable quotes |
| Current | Corporate-bond terms | SEBI-backed Bond Central public database | No API key | Reference terms and ratings; no inferred market price |
| Current | Searchable NSE company catalog | Official NSE equity and SME security-master CSVs | No | Metadata only; refresh daily and load company research on selection |
| Next | Official NSE end-of-day prices/volume | NSE CM-UDiFF Common Bhavcopy Final | No API key | Download official daily report within NSE terms |
| Next | Security master and corporate actions | NSE official reports | No API key | Version every file and effective date |
| Later | Live NSE/BSE quotes and historical candles | Upstox read-only Analytics Token | Upstox account and token | Preferred first broker-authorized live connector |
| Later | Indian macro series | RBI DBIE published downloads | Usually no key | Store release and availability timestamps |
| Optional | Reddit public discussions | Reddit OAuth API | Client ID and client secret | Add only after app approval and policy review |
| Deferred | X posts | Official X API | Paid credentials | Not part of the free baseline |

Do not scrape broker pages, social websites, Screener, TradingView, or exchange web pages
that require a licensed API. A connector is enabled only after its usage and redistribution
terms have been recorded.

## Delivery phases

### B0 — Contracts and India identity

- Canonical stock identity: exchange plus trading symbol, with vendor aliases stored separately
- INR as the default currency for the NSE research universe
- UTC storage with Asia/Kolkata session metadata
- Point-in-time rule: every query is constrained by `available_at`
- Raw payload/file checksum, acquisition run, watermark, and quality quarantine

### B1 — Official end-of-day acquisition

- NSE CM-UDiFF bhavcopy adapter and parser (implemented; scheduling remains)
- Trading-calendar awareness and missing-session detection
- Security-master ingestion and symbol-change history
- Corporate-action records; preserve raw and adjusted price series separately
- Scheduled post-close acquisition with retry and replay by date

### B2 — Deterministic analytics API

- Stock catalog and point-in-time price endpoints
- Returns, SMA, EMA, RSI, MACD, ATR, volatility, drawdown, CVaR, Sharpe, Sortino
- Feature version and methodology metadata
- Data-completeness and stale-input flags

Implemented endpoints in this checkpoint:

- `GET /api/v1/bonds` — stored curve, corporate terms, and deterministic risk flags
- `POST /api/v1/bonds/refresh` — independently refresh CCIL and Bond Central sources
- `POST /api/v1/bonds/calculate` — calculate YTM, duration, convexity, DV01, and rate shocks
  from a user-supplied clean price
- `POST /api/v1/bonds/ladder` — transparent sovereign-curve maturity-bucket model

```text
GET /health
GET /api/v1/dashboard
GET /api/v1/stocks
GET /api/v1/companies/search
GET /api/v1/stocks/{symbol}
GET /api/v1/stocks/{symbol}/prices
GET /api/v1/stocks/{symbol}/technical
GET /api/v1/stocks/{symbol}/disclosures
GET /api/v1/stocks/{symbol}/fundamentals
POST /api/v1/stocks/{symbol}/fundamentals/refresh
GET /api/v1/macro
GET /api/v1/youtube/daily
GET /api/v1/research/{symbol}
POST /api/v1/research/{symbol}/prepare
POST /api/v1/research/{symbol}/explain
```

### Universe expansion policy

Use three deliberately different universes:

1. **Search universe:** every active main-board and SME symbol in the NSE security master.
   Store only lightweight catalog metadata until a company is selected.
2. **Research cache:** the original 20 companies plus any company selected by a user. On first
   selection, acquire sufficient daily history for the deterministic metrics and refresh recent
   Google News metadata. Reuse the stored records on later requests.
3. **Portfolio universe:** target the Nifty 500 rather than every listed security. Maintain its
   historical prices on a schedule and retain sector plus large/mid/small-cap classification.
   Apply liquidity, minimum-history, stale-data, and corporate-action quality gates before a
   company can become a portfolio candidate.

The portfolio universe should not be downloaded synchronously inside a user request. Backfill it
as a controlled batch, then update all 500 from the official daily bhavcopy. This gives useful
large-, mid-, and small-cap breadth without making an interactive request perform hundreds of
vendor calls.

### B3 — Fundamentals and exchange disclosures (prototype implemented)

- Acquire supported official NSE XBRL financial-result documents on demand
- Normalize Indian financial periods, standalone/consolidated scope, units, and revisions
- Retain the original document, checksum, parser version, taxonomy, filing URL, source concept,
  period and point-in-time availability for every normalized fact
- Calculate EBIT, EBITDA, net/operating/EBITDA margins, effective tax rate and interest coverage
  deterministically with the formula attached to each derived fact
- Feed filing facts into the unified research evidence set using stable evidence IDs
- Surface filing facts, deterministic insights, audit status and explicit coverage gaps on the
  Evidence page
- Ingest exchange-filed financial results and corporate announcements from an authorized source
- Calculate ratios from stored statement facts; never accept opaque vendor ratios as canonical
- NSE announcement/XBRL metadata and BSE announcements/result snapshots are normalized with
  dissemination timestamps, raw payloads, and point-in-time availability
- Public website endpoints are not a licensed redistribution feed; production use remains
  gated on exchange terms or a licensed vendor

### B4 — News preprocessing (entity-linking prototype implemented)

- Exact and near-duplicate detection
- Company alias/entity linking with ambiguity rejection
- Language, relevance, event type, and versioned sentiment output
- Retain model name, prompt/config version, evidence IDs, and processing timestamp
- No LLM is required for ingestion; an LLM may later summarize already-linked evidence
- Social comments remain deliberately deferred; selected YouTube channel metadata is implemented

### B5 — Scheduling, caching, and operations

- Worker scheduler with idempotent job keys and bounded retries
- Redis only for cache/queue/locks; PostgreSQL remains the source of truth
- Source health, lag, gap, and failure telemetry for the admin dashboard
- Daily replay jobs and dead-letter handling

### B6 — Unified research snapshot

- One point-in-time snapshot combining prices, features, fundamentals, news, and social evidence
- Explicit missing/stale sections instead of fabricated defaults
- Snapshot version, source lineage, and deterministic input hash
- Stable contract for Option A agents and later Option C attribution experiments

## Credential requests

No credential is required for B1 or B2. Request credentials only at these gates:

1. Before live market data: `UPSTOX_ANALYTICS_TOKEN` from a read-only Upstox developer app.
2. Before YouTube ingestion: `YOUTUBE_API_KEY` restricted to YouTube Data API v3.
3. Before Reddit ingestion: `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` for the approved app.
4. Before optional LLM enrichment: a newly rotated provider key stored only in environment
   configuration. Never commit or paste a key into source, logs, browser code, or prompts.

## Definition of backend complete for Option A

- The 20-stock universe has auditable daily history and corporate-action policy.
- Scheduled ingestion can recover missed dates without duplicates.
- Every feature and content signal is point-in-time reproducible.
- Fundamentals and announcements come from an authorized Indian-market source.
- The unified snapshot reports freshness, lineage, missing data, and feature versions.
- Integration, data-quality, leakage, and failure-recovery tests pass.
- Agents can read snapshots but cannot mutate canonical data or bypass risk services.
