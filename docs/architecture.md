# Data Platform Architecture

## Scope

The first increment establishes the data boundary used by later analytics and agents.
It does not contain LLM logic. Provider-specific payloads enter through adapters and are
converted into stable domain contracts before storage.

## Flow

```text
Vendor API
  -> provider adapter
  -> raw source record
  -> timestamp normalization
  -> schema validation and quality rules
  -> canonical record
  -> atomic repository write
       - raw_records
       - canonical table
       - quality issues
       - ingestion watermark
       - acquisition run
  -> point-in-time repository queries
  -> deterministic analytics
  -> structured research snapshot (claims + evidence IDs + coverage gaps)
  -> prototype Groq synthesis
  -> future ThesisGraph agents and persistent thesis lifecycle
```

Interactive research uses a separate lazy path:

```text
NSE equity + SME security master (symbol metadata only)
  -> server-side company search
  -> user selects one symbol
  -> register that asset
  -> acquire missing/stale research history
  -> refresh linked Google News metadata
  -> build the same point-in-time research snapshot
```

Listing metadata is not treated as preloaded market data. Unselected companies do not create
price, content, disclosure, or analysis records.

## Modules

- `domain`: vendor-neutral Pydantic contracts and enums.
- `data.providers`: source adapters. No agent may call these directly later.
- `data.normalization`: timestamp and field normalization with quality checks.
- `db`: SQLAlchemy tables and a repository that owns persistence semantics.
- `services`: ingestion orchestration and run lifecycle.
- `analytics`: deterministic, point-in-time price and risk calculations.
- `research`: structured evidence/claim snapshots and the replaceable LLM synthesis boundary.
- `cli`: development and batch-operation entry points.

The Groq adapter is not a financial calculator or a data provider. It receives a bounded
snapshot from `research`, returns a validated narrative schema, and is never called from the
browser. Successful responses are retained in `research_analyses` with the exact snapshot hash.

## Storage strategy

PostgreSQL is the primary database. Each acquisition retains the original record in
`raw_records`, while canonical tables support efficient research queries. Upserts make
repeated ingestion idempotent. Raw payload checksums support change detection and audit.

Primary indexes follow the access pattern: asset plus event time, and asset plus
availability time. Historical research always constrains `available_at`.

## Failure behavior

One malformed vendor record creates a data-quality issue and does not invalidate valid
records in the same response. Transport or authentication failures fail the acquisition
run and do not advance its watermark. A completed batch, its records, issues, and
watermark are committed together.
