# System Invariants

1. Historical queries never return a record whose `available_at` is after the cutoff.
2. All timestamps crossing module boundaries are timezone-aware UTC values.
3. Provider payloads are retained before or alongside canonical records.
4. Reprocessing the same provider record is idempotent.
5. Vendor-specific schemas do not leak into analytics or future agent contracts.
6. Invalid records are quarantined and observable, never silently corrected.
7. Failed acquisition runs do not advance watermarks.
8. Credentials come from environment variables and never from committed source.
9. Deterministic calculations will consume canonical records, not free-form text.
10. Agents will never execute real trades.

