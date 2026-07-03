# Clarify-Produced Data Processing

`scripts/process_clarify_evidence_data.py` consumes a Clarify-produced evidence
bundle and writes deterministic Ailuros validation artifacts into that same
bundle directory.

The processor is offline only:

- no LLM calls
- no HTTP calls
- no runtime policy execution
- no blocking, approval, or human-review action

## Command

```bash
python scripts/process_clarify_evidence_data.py --bundle <bundle-dir>
```

Example:

```bash
python scripts/process_clarify_evidence_data.py --bundle examples/clarify/evidence_bundle.sample
```

## Inputs

Expected bundle files:

- `manifest.json`
- `ailuros.timeline.v0.json`
- `clarify-validation.log`
- `clarify-validation-result.json`
- `README.md`

## Outputs

The processor writes:

- `ailuros-validation-result.json`
- `ailuros-validation-report.md`

The result schema is `ailuros.validation_result.v0` with source `clarify` and
final status `PASS`, `WARN`, or `FAIL`.

## Status Rules

- Any P0 failure returns `FAIL`.
- Any P1 failure returns `FAIL`.
- P2 warnings without failures return `WARN`.
- Clarify validation status `skipped` returns `WARN`.
- No failures or warnings returns `PASS`.

Exit code is `1` for `FAIL` and `0` for `PASS` or `WARN`.

## Boundary Checks

The processor scans the bundle JSON files for forbidden runtime or policy keys:

- `policy_decision`
- `approval_status`
- `human_review_required`
- `policy_action`
- `blocking_action`
- `runtime_blocked`

It also warns on suspicious secret-like keys and local machine path references.
Generated result artifacts avoid embedding local absolute bundle paths.

## Validation

```bash
python -m pytest tests/test_process_clarify_evidence_data.py -q
python scripts/process_clarify_evidence_data.py --bundle examples/clarify/evidence_bundle.sample
```
