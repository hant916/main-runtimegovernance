# ADR-0004: Evidence-First Deterministic Read-Side Projection

**Status:** Accepted

**Date:** 2026-08-08

## Context

Ailuros stores evidence in two forms: as `RuntimeEvent` timeline entries in SQLite
and as `EvidencePackage` bundles loaded from disk. The v1.5 post-run governance
pipeline consumes these directly — loading, validating, and producing an
`AuditResult` — but each consumer (audit, report, CLI) queries raw events
independently, duplicating filtering and transformation logic.

New cross-run product needs are emerging. EverRun requires per-run execution
projections (tool calls, sequence, outcomes, errors) and governance signals
(pass/warn/fail audit decisions with evidence references). radarCreation will need
domain-specific projections over the same evidence store. Without an explicit
boundary, each product would couple to raw `RuntimeEvent` internals, creating
fragile read paths that scatter event-type filtering, payload parsing, and
data-shape assumptions across consumer code.

Direct UI or product-code coupling to raw `RuntimeEvent` streams is rejected
because it forces consumers to know internal event vocabulary, duplicates
transformation logic, and makes the read path hard to change without breaking
every dashboard, CLI, or report simultaneously.

## Decision

Ailuros adopts a **deterministic read-side projection** layer between stored
evidence and all downstream consumers:

1. **Evidence is immutable.** Once stored as a `RuntimeEvent` in SQLite, an event
   is never altered. The event timeline is the single source of truth.

2. **Projection is deterministic.** Given the same set of stored events, the
   projection produces byte-identical results. Projections are derived
   mechanically from evidence only — no randomness, no external state, no LLM
   participation in fact derivation.

3. **Signals are evidence-linked.** Every governance signal (pass, warn, fail,
   policy violation, or warning) carries a reference to the source evidence
   record (event ID, sequence number, or contract rule). A signal without an
   evidence reference is a projection defect.

4. **UI and product views are read-only.** Console, dashboards, and product
   views consume the projection layer; they never query raw events directly and
   add no governance logic.

5. **No LLM fact derivation.** Projection facts (tool was called, sequence
   position, outcome, error) are derived from event fields only. LLM-generated
   summaries or interpretations are analysis, not evidence, and must be rendered
   in visually separate blocks from observed facts.

The projection is organized into two deterministic levels:

| Level | Output | Description |
|---|---|---|
| ExecutionProjection | Tool calls, sequence ordering, outcomes, errors | Machine-readable execution facts derived mechanically from stored events |
| GovernanceSignal | Audit decision (pass/warn/fail), contract validation result, policy evaluation outcomes | Governance interpretation with evidence references |

## Consequences

- Projection outputs can be dropped and rebuilt at any time from the stored
  evidence alone. No data loss occurs.
- Each product (EverRun, radarCreation, Clarify) defines its own projection
  consumer but shares the same projection layer. Product-specific interpretation
  lives in the consumer, not in `src/ailuros/`.
- Adapter code (`src/ailuros/adapters/`) remains outside core-specific coupling.
  No adapter imports product-specific or UI concepts.
- The projection contract becomes a stability boundary: projection output
  schemas must be versioned alongside the evidence contract.
- Console dashboards and reports become cheaper to build because they consume
  pre-derived facts rather than raw event streams.

## Alternatives Rejected

### Dashboard scanning native history

A dashboard that queries raw `RuntimeEvent` rows, filters by `event_type`, and
parses payloads directly couples presentation to internal event vocabulary.
Every event-type rename or payload reshape breaks every dashboard and report
simultaneously. The projection layer isolates this churn.

### Giant universal status enum

A single status enum covering all possible product meanings (pass, warn, fail,
blocked, pending_review, etc.) forces every product into the same classification
scheme. Different products need different views of the same evidence. The
projection layer lets each consumer derive its own status from shared facts.

### Premature ClickHouse/OTel pipeline

Introducing ClickHouse, OpenTelemetry collectors, or streaming query pipelines
before the local-projection model is validated adds infrastructure complexity
and operations cost without a proven need. A local deterministic projection over
SQLite-evidence is sufficient for the current scale and can inform future
infrastructure decisions once aggregation patterns are stable.
