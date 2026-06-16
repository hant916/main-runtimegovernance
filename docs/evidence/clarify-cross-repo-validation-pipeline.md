# Clarify Cross-Repo Validation Pipeline

## Status

Offline evidence-only validation pipeline that drives Clarify evidence export and
Ailuros bundle validation from a single local command.

## Scope

| Layer | Included | Rationale |
|---|---|---|
| Clarify npm export | Yes | `npm run ailuros:evidence` via subprocess |
| Bundle copy | Yes | `artifacts/ailuros/latest/` → output directory |
| Ailuros bundle validation | Yes | `validate_clarify_evidence_bundle.py` |
| Missing-bundle failure report | Yes | JSON + Markdown if Clarify bundle absent |
| Stdlib-only runner | Yes | No external dependencies |
| Skip flag for test/dev | Yes | `--skip-clarify-command` |
| HTTP or service integration | **No** | Explicitly excluded by red lines |
| Policy execution | **No** | Explicitly excluded by red lines |
| Clarify code import | **No** | Invoked via subprocess only |

## Pipeline Script

`scripts/run_clarify_validation_pipeline.py`

- CLI:
  ```
  python scripts/run_clarify_validation_pipeline.py --clarify-root <path> --output <path>
  ```
- Optional `--skip-clarify-command` to copy an existing bundle without running npm.
- Exit codes: 0 (pass), 1 (fail).
- Prints final status: `Ailuros Clarify validation: PASS|WARN|FAIL`.

## Output Files

| File | Description |
|---|---|
| `manifest.json` | Copied from Clarify bundle |
| `ailuros.timeline.v0.json` | Copied from Clarify bundle |
| `clarify-validation.log` | Copied from Clarify bundle |
| `clarify-validation-result.json` | Copied from Clarify bundle |
| `README.md` | Copied from Clarify bundle |
| `ailuros-validation-result.json` | Ailuros validation result |
| `ailuros-validation-report.md` | Ailuros validation report |

## Operator Command (Windows PowerShell)

```powershell
python scripts/run_clarify_validation_pipeline.py `
    --clarify-root C:\Workspace-Sel\31-claritynow `
    --output .ailuros/evidence/clarify/latest
```

## Important Notes

- This is **offline evidence-only validation**, not runtime governance enforcement.
- The Clarify repo is never modified by this script.
- If the Clarify `npm run ailuros:evidence` command fails but
  `artifacts/ailuros/latest/` still exists (e.g. from a prior run), the pipeline
  continues with validation because partial failure evidence is still useful.
- If the bundle is completely missing, a failure JSON report and Markdown report
  are written to the output directory.

## Validation Commands

```bash
python scripts/run_clarify_validation_pipeline.py --help
python -m pytest tests/test_run_clarify_validation_pipeline.py -q
```

## References

- `scripts/validate_clarify_evidence_bundle.py` — Offline bundle validator
- `docs/evidence/clarify-evidence-bundle-validation.md` — Bundle validation docs
- `docs/evidence/clarify-contract-validation.md` — Contract validation docs
