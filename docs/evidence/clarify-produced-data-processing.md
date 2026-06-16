# Clarify-Produced Data Processing

## Overview

`scripts/process_clarify_evidence_data.py` is a thin CLI orchestrator that turns a Clarify-produced evidence bundle into deterministic Ailuros PASS/WARN/FAIL result artifacts.

It delegates all validation logic to `scripts/validate_clarify_evidence_bundle.py` and adds a raw log existence/size sanity check.

## Architecture

```
process_clarify_evidence_data.py  (orchestrator / entry point)
  └── validate_clarify_evidence_bundle.py  (validation logic)
        ├── validate_bundle()  → checks, status
        ├── write_results()    → ailuros-validation-result.json
        └──                    → ailuros-validation-report.md
```

## CLI Usage

```bash
python scripts/process_clarify_evidence_data.py --bundle <bundle-dir>
```

### Exit codes

| Exit Code | Meaning |
|-----------|---------|
| 0         | PASS or WARN (validation passed with warnings) |
| 1         | FAIL (blocking validation issue) |

## Validation Scope

All checks defined in the bundle validator apply:

### Bundle integrity (P0)
- Bundle directory exists
- `manifest.json` is present and valid JSON
- `manifest.schema_version` is `ailuros.evidence_bundle.v0`
- `manifest.producer` is `clarify`
- `manifest.artifacts` present and all files exist

### Timeline contract (P1)
- `ailuros.timeline.v0.json` is valid JSON
- `schema_version` is `ailuros.timeline.v0`
- `run_id` and `created_at` present
- Exactly 6 events in required order
- Each event has `event`, `run_id`, `timestamp`, and `data` or `metadata`
- `EVALUATION_RESULT` has `data.quality_signals` with 5 boolean fields

### Clarify validation result (P1)
- Valid JSON
- `schema_version` is `clarify.validation_result.v0`
- `status` is `passed` or `failed` (must be `passed`)
- `commands` array with required fields

### Evidence-only boundary
- Forbidden keys: `policy_decision`, `approval_status`, `human_review_required`, `policy_action`, `blocking_action`, `runtime_blocked`
- Warnings for secret-like keys
- Warnings for local machine path references

### Raw log sanity
- `clarify-validation.log` exists, is non-empty, and within size limits

## Validation Commands

```bash
python scripts/process_clarify_evidence_data.py --bundle examples/clarify/evidence_bundle.sample
python -m pytest tests/test_process_clarify_evidence_data.py -q
python -m pytest tests/test_clarify_evidence_bundle_validation.py -q
```

## References

- `docs/evidence/clarify-evidence-bundle-validation.md` — detailed bundle validation spec
- `scripts/validate_clarify_evidence_bundle.py` — validation implementation
- `examples/clarify/evidence_bundle.sample/` — sample evidence bundle
