# ADR 0002: Retain raw data and canonical point-in-time records in PostgreSQL

## Status

Accepted

## Decision

Store immutable raw provider records and normalized research records. Every canonical
record includes `available_at`, and every historical repository method requires a cutoff.

## Consequences

Storage use is higher than a canonical-only design, but acquisitions remain auditable and
reprocessable. PostgreSQL indexes support the initial research scale without adding a
separate time-series database.

