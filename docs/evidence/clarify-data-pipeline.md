# Clarify Data Pipeline

## Status

Offline evidence-only pipeline that runs Clarify's data production and
processes the resulting bundle through Ailuros validation.

## Scope

| Layer | Included | Rationale |
|---|---|---|
| Clarify npm data production | Yes | `npm run ailuros:produce-data` via subprocess |
| Profile forwarding | Yes | `--profile` forwarded to npm script |
| Bundle copy | Yes | `artifacts/ailuros/latest/` to output directory |
| Ailuros bundle processing | Yes | `process_clarify_evidence_data.py` |
| Missing-bundle failure report | Yes | JSON + Markdown if Clarify bundle absent |
| Stdlib-only runner | Yes | No external dependencies |
| Skip flag for test/dev | Yes | `--skip-clarify-command` |
| HTTP or service integration | **No** | Explicitly excluded by red lines |
| Policy execution | **No** | Explicitly excluded by red lines |
| Clarify code import | **No** | Invoked via subprocess only |

## Pipeline Script

`scripts/run_clarify_data_pipeline.py`

- CLI:
  ```
  python scripts/run_clarify_data_pipeline.py --clarify-root <path> --output <path>
  ```
- Optional `--profile` forwards a profile value to `npm run ailuros:produce-data`.
- Optional `--skip-clarify-command` to reuse an existing bundle without running npm.
- Exit codes: 0 (pass), 1 (fail).
- Prints final status: `Ailuros Clarify data pipeline: PASS|WARN|FAIL`.

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
python scripts/run_clarify_data_pipeline.py `
    --clarify-root C:\Workspace-Sel\31-claritynow `
    --output .ailuros/evidence/clarify/latest
```

With profile:

```powershell
python scripts/run_clarify_data_pipeline.py `
    --clarify-root C:\Workspace-Sel\31-claritynow `
    --output .ailuros/evidence/clarify/latest `
    --profile staging
```

## Important Notes

- This is **offline evidence-only processing**, not runtime governance enforcement.
- The Clarify repo is never modified by this script.
- If the Clarify `npm run ailuros:produce-data` command fails but
  `artifacts/ailuros/latest/` still exists (e.g. from a prior run), the pipeline
  continues with processing because partial failure evidence is still useful.
- If the bundle is completely missing, a failure JSON report and Markdown report
  are written to the output directory.

## Validation Commands

```bash
python scripts/run_clarify_data_pipeline.py --help
python -m pytest tests/test_run_clarify_data_pipeline.py -q
```

## References

- `scripts/process_clarify_evidence_data.py` — Offline bundle processor
- `scripts/validate_clarify_evidence_bundle.py` — Offline bundle validator
- `docs/evidence/clarify-evidence-bundle-validation.md` — Bundle validation docs
