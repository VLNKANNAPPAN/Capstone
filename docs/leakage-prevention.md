# Leakage Prevention

## Admission rule

For a simulated decision at time `T`, a record is eligible only when:

```text
record.available_at <= T
```

Filtering by event date alone is insufficient. A quarterly result can describe an old
period while becoming public months later.

## Source rules

- A market bar becomes available only after its interval closes.
- An SEC filing becomes available at its acceptance timestamp.
- News and macro adapters must preserve both event and publication or release times.
- Missing availability metadata is a quality failure, not permission to infer an early
  timestamp.

## Test requirements

Repository tests must insert records on both sides of a cutoff and prove that only
eligible records are returned. Future provider adapters must add equivalent fixture-based
tests before being used in research experiments.

