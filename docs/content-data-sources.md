# News and Social Data Plan

## Principles

- Store source content and timestamps before deriving sentiment.
- Keep `published_at`, `available_at`, and `ingested_at` separate.
- Link every derived signal to the source item and model version.
- Never treat engagement as sentiment or popularity as correctness.
- Do not scrape platforms whose official API or license is required.

## News

Two no-key discovery connectors are available:

- GDELT DOC 2.0 remains the broad primary candidate, but shared-IP throttling is treated as
  a degraded source state and never worked around with duplicate records.
- Google News RSS is a development fallback. It stores metadata and publisher links only,
  excludes social domains, and is restricted by the feed terms to personal,
  non-commercial use. It is not a production redistribution source.

The RSS pipeline accepts an item only when a configured company name or unambiguous ticker
alias occurs in the headline. It records the alias, method, confidence, publisher, canonical
headline, and original provider identifier. Exact canonical-headline duplicates are removed
from the research snapshot.

For production-quality Indian financial news, add a licensed provider behind the same
`ContentProvider` contract. Provider migration must not change the normalized content
schema or dashboard API.

## Social

Social ingestion remains credential-gated:

1. Reddit: use an approved OAuth application and read-only endpoints for explicitly chosen
   communities. Preserve post identifiers, timestamps, scores, comment counts, and links.
2. YouTube: the official Data API is now connected for CNBC-TV18, ET NOW, Moneycontrol,
   NDTV Profit, and Money Pechu. Video comments remain deferred.
3. X: use an official paid API plan if it becomes necessary; do not scrape the website.

The platform should collect only public content required for research, retain no private
profile information, respect deletion and retention obligations, and never display author
identity as a decision signal.

## Processing stages

1. Exact provider-ID and canonical-headline deduplication
2. Near-duplicate title detection (next production step)
3. Language identification
4. Company/entity linking with aliases and ambiguity rules
5. Relevance classification
6. Sentiment and event classification with a versioned model
7. Aggregation by symbol and decision-time window

Sentiment scores must include sample count, dispersion, source mix, and model version. A
single mean score without those diagnostics is not decision-grade evidence.

## Scheduling

- News discovery: every 15 minutes, with provider-specific backoff and cached replay
- Social sources: every 15-30 minutes within the provider's documented rate limit
- Deduplication and entity linking: after each ingestion batch
- Sentiment aggregation: hourly and at the research decision cutoff

Failed windows are replayed from their watermark. No scheduler should silently advance a
watermark after a partial or failed acquisition.

## YouTube daily digest

The adapter resolves each configured channel, reads its uploads playlist, and batches video
detail requests. This avoids using the much more expensive search endpoint for recurring
polls. It stores title, shortened description, publication time, duration, public engagement
counts, channel identity, and conservatively linked research-universe symbols.

Run `capstone-data ingest-youtube --lookback-hours 48 --max-per-channel 10`. The normalized
IST-day view is available at `GET /api/v1/youtube/daily`. The digest is explicitly
metadata-based: it does not download media or claim to summarize transcripts.
