# Clarify Evidence Bundle Validation — Offline

## Status

Offline evidence bundle validation for Clarify-produced Ailuros evidence bundles.

## Scope

| Layer | Included | Rationale |
|---|---|---|
| Offline CLI validation | Yes | `scripts/validate_clarify_evidence_bundle.py` |
| P0 bundle integrity | Yes | manifest, artifacts, required files |
| P1 timeline contract | Yes | schema, events, order, quality_signals |
| Clarify validation result | Yes | schema, status, commands |
| Evidence-only boundary | Yes | forbidden keys, secret detection, local path warnings |
| Machine/human reports | Yes | JSON result + Markdown report |
| Sample bundle | Yes | `examples/clarify/evidence_bundle.sample/` |
| Focused pytest coverage | Yes | `tests/test_clarify_evidence_bundle_validation.py` |
| HTTP ingestion API | **No** | Explicitly excluded by red lines |
| Policy decisions | **No** | Explicitly excluded by red lines |
| Storage or DB schema | **No** | Explicitly excluded by red lines |
| Clarify source import | **No** | Explicitly excluded by red lines |
| LLM calls | **No** | Explicitly excluded by red lines |

## Validator

`scripts/validate_clarify_evidence_bundle.py`

- Standalone offline script (stdlib only)
- CLI: `python scripts/validate_clarify_evidence_bundle.py --bundle <bundle-dir>`
- Exit codes: PASS=0, WARN=0, FAIL=1
- Writes `ailuros-validation-result.json` and `ailuros-validation-report.md`

## Validated Checks (P0)

- Bundle directory exists
- `manifest.json` is present and valid JSON
- `manifest.schema_version` is `ailuros.evidence_bundle.v0`
- `manifest.producer` is `clarify`
- `manifest.artifacts` is present and all artifacts exist on disk
- `ailuros.timeline.v0.json` is present
- `clarify-validation-result.json` is present

## Validated Checks (P1 — Timeline)

- Timeline JSON is valid
- `schema_version` is `ailuros.timeline.v0`
- `run_id` and `created_at` are present
- `events` is an array of exactly 6 events
- Event order: INPUT_CLASSIFIED, LLM_REQUEST, LLM_RESPONSE, EVALUATION_RESULT, OUTPUT_GENERATED, RUN_COMPLETED
- Each event has `event`, `run_id`, `timestamp`
- Each event has `data` or `metadata`
- EVALUATION_RESULT has `data.quality_signals` with required boolean fields

## Validated Checks (P1 — Clarify Validation Result)

- Valid JSON
- `schema_version` is `clarify.validation_result.v0`
- `status` is `passed` or `failed` (must be `passed`)
- `commands` is an array with required fields

## Evidence-Only Boundary Checks

- Forbidden runtime/policy keys: `policy_decision`, `approval_status`, `human_review_required`, `policy_action`, `blocking_action`, `runtime_blocked`
- Warnings for secret-like keys: token, password, secret, api_key, apikey, authorization, bearer
- Warnings for local path references: `C:\`, `/Users/`, `.everrun`, `node_modules`
- Warning if `manifest.runtime_integration` is absent

## Validation Commands

```bash
python scripts/validate_clarify_evidence_bundle.py --bundle examples/clarify/evidence_bundle.sample
python -m pytest tests/test_clarify_evidence_bundle_validation.py -q
```

## Sample Bundle

`examples/clarify/evidence_bundle.sample/` — minimal valid bundle

## References

- `docs/evidence/clarify-contract-validation.md` — Phase 1.5 offline contract validation
- `scripts/check_evidence_boundary.py` — evidence pipeline boundary checks
