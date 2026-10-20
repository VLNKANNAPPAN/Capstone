# ADR 0003: ThesisGraph Prototype Boundary

## Status

Accepted for the single-model prototype.

## Context

The research direction requires persistent, temporally aware claims connected to auditable
evidence. The production design will eventually use specialist agents, Bull/Bear debate, a
persistent thesis lifecycle, targeted re-evaluation, and deterministic portfolio services.
Implementing that complete graph before the India data foundation is reliable would make it
easy for model prose to outrun the available evidence.

## Decision

The prototype introduces a narrow compatibility boundary:

1. `ResearchSnapshotService` converts point-in-time backend metrics and stored content into
   structured evidence and claims.
2. Every evidence item has a stable ID, category, direction, timestamp, freshness, and source.
3. Missing fundamentals, macro, news, or social evidence is represented explicitly.
4. One Groq model may synthesize the snapshot, but it may not calculate financial metrics or
   introduce unsupported evidence.
5. Groq returns a validated schema containing explanations, support, contradictions, scenarios,
   assumptions, thesis breakers, confidence, and data gaps.
6. Each synthesis is stored with the model, prompt version, snapshot hash, request, response, and
   timestamp.

## Consequences

- The current UI is a usable single-model baseline for the later research evaluation.
- The LLM can be replaced by agent orchestration without changing the deterministic snapshot.
- Stored analyses are not yet persistent investment theses; thesis versioning and change
  detection remain later phases.
- Evidence gaps remain visible instead of being filled with generated facts.
