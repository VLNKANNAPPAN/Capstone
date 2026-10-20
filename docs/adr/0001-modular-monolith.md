# ADR 0001: Begin as a modular monolith

## Status

Accepted

## Decision

Use one Python package and one PostgreSQL database with explicit module boundaries.
Do not introduce microservices, Kafka, or a background worker until measured workload or
failure-isolation requirements justify them.

## Consequences

Development, transactions, and testing remain simple. Provider and repository protocols
preserve extraction boundaries if deployment later needs to split.

