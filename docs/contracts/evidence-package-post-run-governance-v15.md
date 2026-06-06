# Evidence Package Post-Run Governance Contract (v1.5)

**Status:** Accepted

**Date:** 2026-06-06

## Purpose

This contract defines **v1.5 post-run governance**: a minimal, source-neutral
audit that consumes a completed run's canonical evidence package and produces a
single pass/warn/fail decision describing the quality of the captured evidence.

v1.5 is **post-run validation, not runtime governance.** It runs *after* a run
has finished and only inspects the evidence the run left behind. It never sees,
intercepts, or controls live execution.

## Not Runtime Governance

The audit deliberately has no runtime control surface:

- There is **no** allow / warn / review / block runtime API.
- There is **no** `BLOCKED` or `HUMAN_REVIEW` path introduced by this contract.
- There is **no** policy DSL, custom policy pack, HTTP ingestion, database
  persistence, or release blocking.

The output is an after-the-fact judgement, equivalent to a lint result for an
evidence package. Acting on the decision (if at all) is left to the caller.

## Decision Semantics

The audit emits exactly one `AuditDecision`, with exactly three values:

| Decision | Meaning | Condition |
|---|---|---|
| `pass` | Evidence is clean and contract-valid. | No errors and no warnings. |
| `warn` | Evidence is valid but has tolerated anomalies. | No errors, one or more warnings. |
| `fail` | Evidence violates the package contract. | One or more errors. |

`fail` always takes priority: if any error exists the decision is `fail`, even
when warnings are also present. Warnings are still surfaced in the result.

The result also carries source-neutral context: `ok` (true unless `fail`),
`governance_mode`, `source`, `schema_version`, `run_id`, `events_count`,
`rules_evaluated`, and the ordered `warnings` and `errors` lists.

## Rules

The rule set is minimal and reads only the generic contract `ValidationResult`.
It encodes **no producer-specific risk semantics.**

1. **Errors fail** — any contract validation error produces `fail`.
2. **Warnings warn** — any contract validation warning, with no errors, produces
   `warn`.

A clean validated package matches neither rule and produces `pass`. Examples of
inputs that map to warnings (and therefore `warn`) include well-formed events
whose `event_type` is outside the canonical vocabulary; examples that map to
errors (and therefore `fail`) include a missing required file or a malformed
timeline. See the contract validator for the full validation surface.

## Report Output

The result serializes to stable, JSON-compatible data:

- `audit_result_to_dict(result)` returns plain JSON-serializable values.
- `audit_result_to_json(result)` returns deterministic JSON text (sorted keys).

Warning and error order is preserved exactly as validation produced it, which is
deterministic for a given package. Markdown rendering is intentionally **not**
part of v1.5.

## Public Surface

Exposed from `ailuros.adapters.evidence_package`:

- `audit_evidence_package(package_dir) -> AuditResult`
- `audit_result_to_dict(result) -> dict`
- `audit_result_to_json(result) -> str`

The `AuditResult` and `AuditDecision` types live in `ailuros.core.audit`.
