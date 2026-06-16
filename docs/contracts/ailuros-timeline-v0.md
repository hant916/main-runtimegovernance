# Ailuros Timeline v0 — Offline Evidence Contract

**Status:** Accepted

**Date:** 2026-06-17

## Purpose

This contract defines the `ailuros.timeline.v0` JSON Schema artifact and its
semantic constraints. It governs the format of governance timeline evidence
produced by reference applications (e.g. Clarify) for offline validation.

This is an **offline evidence contract**, not an HTTP ingestion API. The
timeline is written to disk as a JSON file and validated by
`scripts/validate_clarify_evidence_bundle.py`.

## Scope

| Layer | Included | Rationale |
|---|---|---|
| JSON Schema document | Yes | `schemas/ailuros.timeline.v0.schema.json` |
| Offline Python validation | Yes | `scripts/validate_clarify_evidence_bundle.py` (stdlib, no JSON Schema dep) |
| Focused pytest coverage | Yes | `tests/test_ailuros_timeline_schema.py` |
| HTTP ingestion API | **No** | Explicitly excluded by red lines |
| Policy decisions | **No** | Explicitly excluded by red lines |
| Storage or DB schema | **No** | Explicitly excluded by red lines |

## Top-Level Fields

| Field | Type | Required | Constraint |
|---|---|---|---|
| `schema_version` | string | Yes | Must be `"ailuros.timeline.v0"` |
| `run_id` | string | Yes | Non-empty |
| `created_at` | string | Yes | Non-empty |
| `events` | array | Yes | Array of event objects |

## Required Event Order

Events MUST appear in the following order:

1. `INPUT_CLASSIFIED`
2. `LLM_REQUEST`
3. `LLM_RESPONSE`
4. `EVALUATION_RESULT`
5. `OUTPUT_GENERATED`
6. `RUN_COMPLETED`

## Required Event Fields

Each event object MUST contain:

| Field | Type | Constraint |
|---|---|---|
| `event` | string | One of the six allowed names (see below) |
| `run_id` | string | Non-empty |
| `timestamp` | string | Non-empty |

Allowed event names:

- `INPUT_CLASSIFIED`
- `LLM_REQUEST`
- `LLM_RESPONSE`
- `EVALUATION_RESULT`
- `OUTPUT_GENERATED`
- `RUN_COMPLETED`

Each event MAY contain `metadata` (object) and/or `data` (object). No other
keys are permitted at the event level.

## EVALUATION_RESULT — quality_signals

The `EVALUATION_RESULT` event MUST contain `data.quality_signals` with the
following required boolean fields:

| Signal | Type |
|---|---|
| `json_valid` | boolean |
| `sentence_too_long` | boolean |
| `contains_direct_advice` | boolean |
| `contains_decision_pressure` | boolean |
| `ambiguities_present` | boolean |

These constraints are enforced by the **Python validator**
(`scripts/validate_clarify_evidence_bundle.py`) rather than by the JSON Schema
`if`/`then` conditional, because JSON Schema conditional logic for nested
required fields with type constraints adds unnecessary complexity. The schema
remains a readable contract artifact; effective validation lives in Python.

## Evidence-Only Forbidden Fields

The following fields MUST NOT appear anywhere in the timeline (nor in the
bundle manifest or Clarify validation result):

- `policy_decision`
- `approval_status`
- `human_review_required`
- `policy_action`
- `blocking_action`
- `runtime_blocked`

These are runtime/policy-layer concepts that must not leak into offline
evidence.

## Schema Location

`schemas/ailuros.timeline.v0.schema.json`

## Validation

```bash
# Offline bundle validator (stdlib Python)
python scripts/validate_clarify_evidence_bundle.py --bundle examples/clarify/evidence_bundle.sample

# Schema contract tests
python -m pytest tests/test_ailuros_timeline_schema.py -q
```

## Related Documents

- `docs/evidence/clarify-evidence-bundle-validation.md` — full bundle validation pipeline
- `docs/contracts/phase1-evidence-only-contract.md` — Phase 1 evidence-only boundary
- `schemas/ailuros.timeline.v0.schema.json` — JSON Schema artifact
- `examples/clarify/evidence_bundle.sample/ailuros.timeline.v0.json` — valid sample
