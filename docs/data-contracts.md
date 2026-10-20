# Data Contracts

## Time semantics

- `event_time`: when the represented market or business event occurred.
- `published_at`: when a publisher says a document or event was published, when known.
- `available_at`: earliest defensible time the research system could have observed it.
- `ingested_at`: when this platform received and stored it.

`available_at` is the only timestamp used to admit data into a historical decision.
`ingested_at` supports operational auditing but must not replace it.

## Price bars

Price bars contain a symbol, timeframe, UTC start time, OHLCV fields, optional VWAP and
trade count, source, availability time, and ingestion time. A bar becomes available at
the end of its interval, not at its opening timestamp.

## Fundamental documents

SEC filing metadata uses the accession number as the provider natural key. The SEC
acceptance timestamp is the availability timestamp. Records without a parseable
acceptance timestamp are quarantined instead of assigned an invented time.

## Raw records

Raw records preserve provider fields, a stable natural key, timestamps, and a SHA-256
checksum of canonical JSON. They allow later reprocessing without reacquiring data.

