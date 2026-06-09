# Clarify Timeline Contract Validation — Phase 1.5 Offline

## Status

Phase 1.5 — offline contract validation. This is **not** Phase 2 HTTP ingestion.

## Scope

| Layer | Included | Rationale |
|---|---|---|
| Offline fixture import | Yes | Canonical sample copied to `tests/fixtures/clarify/` |
| Schema contract validation | Yes | `scripts/check_clarify_timeline_contract.py` validates schema_version, event ids, event types, timestamps, payload shape |
| Focused pytest coverage | Yes | `tests/test_clarify_timeline_contract.py` covers the valid fixture |
| HTTP ingestion API | **No** | Explicitly excluded by red lines |
| Persistent event store | **No** | Explicitly excluded by red lines |
| Clarify source-code import | **No** | Explicitly excluded by red lines |
| Production runtime transport | **No** | Explicitly excluded by red lines |
| Policy engine expansion | **No** | Explicitly excluded by red lines |

## Fixture Location

`tests/fixtures/clarify/clarify_timeline_v0.sample.json`

Copied from the Clarify canonical Ailuros timeline sample at `examples/ailuros/clarify_timeline_v0.sample.json`.

## Validator

`scripts/check_clarify_timeline_contract.py`

- Standalone offline script (stdlib only)
- Returns `PASS` or `FAIL` summary with details
- Validates: schema_version, run_id, created_at, events array, event types, event ids, timestamps (ISO 8601 UTC), and payload object shape

## Contract Checks

- `schema_version` must be `"ailuros.timeline.v0"`
- `run_id` must be a non-empty string
- `created_at` must be a non-empty string
- `events` must be a non-empty array of objects
- Each event must have: `event` (string), `run_id` (string), `timestamp` (ISO 8601 UTC string)
- Each event may have: `id` (non-empty string), `metadata` or `data` (object)
- All six required event types must be present

## Validation Commands

```bash
python scripts/check_clarify_timeline_contract.py
python -m pytest tests/test_clarify_timeline_contract.py -q
```

## Required Event Types

- `INPUT_CLASSIFIED`
- `LLM_REQUEST`
- `LLM_RESPONSE`
- `EVALUATION_RESULT`
- `OUTPUT_GENERATED`
- `RUN_COMPLETED`

## References

- `src/ailuros/adapters/clarify_timeline_contract.py` — existing Ailuros timeline contract
- `docs/reference-apps/clarify-timeline-validation.md` — earlier Phase 1 validation docs
