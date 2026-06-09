# Clarify Governance Timeline JSON Schema Contract — Phase 1.5

## Status

Phase 1.5 contract hardening. This is **not** Phase 2 HTTP transport.

## Scope

| Layer | Included | Rationale |
|---|---|---|
| JSON Schema document | Yes | `schemas/clarify-governance-timeline.schema.json` |
| Offline schema validation | Yes | `scripts/check_clarify_governance_timeline_schema.py` |
| Focused pytest coverage | Yes | `tests/test_ailuros_contract_compliance.py` |
| HTTP ingestion API | **No** | Explicitly excluded by red lines |
| OpenAPI spec generation | **No** | Explicitly excluded by red lines |
| Runtime code generation | **No** | Explicitly excluded by red lines |
| Clarify runtime modifications | **No** | Explicitly excluded by red lines |
| Production backend config | **No** | Explicitly excluded by red lines |

## Schema Location

`schemas/clarify-governance-timeline.schema.json`

JSON Schema (draft 2020-12) for the Clarify-produced Ailuros governance timeline contract.

### Contract Rules

- `schema_version` must be `"ailuros.timeline.v0"`
- `run_id` must be a non-empty string
- `created_at` must be a non-empty string
- `events` must be a non-empty array of objects
- Each event must have: `event` (non-empty string), `run_id` (non-empty string), `timestamp` (non-empty string)
- Each event may have: `metadata` (object), `data` (object) — nested payload validation is intentionally loose
- Six required event types: `INPUT_CLASSIFIED`, `LLM_REQUEST`, `LLM_RESPONSE`, `EVALUATION_RESULT`, `OUTPUT_GENERATED`, `RUN_COMPLETED`

## Fixture

`tests/fixtures/clarify/clarify_timeline_v0.sample.json`

Referenced from the canonical sample at `examples/ailuros/clarify_timeline_v0.sample.json`.

## Validator

`scripts/check_clarify_governance_timeline_schema.py`

- Standalone offline script (stdlib only)
- Loads the JSON Schema document and validates the fixture against it
- Returns `PASS` or `FAIL` summary with details

## Validation Commands

```bash
python scripts/check_clarify_governance_timeline_schema.py
python -m pytest tests/test_ailuros_contract_compliance.py -q
```

## Related Documents

- `docs/evidence/clarify-contract-validation.md` — Phase 1.5 offline contract validation (adapter-level)
- `schemas/clarify-governance-timeline.schema.json` — declarative JSON Schema contract
