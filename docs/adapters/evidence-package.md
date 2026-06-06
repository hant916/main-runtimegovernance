# Evidence Package Adapter

The evidence-package adapter audits a completed run's **canonical evidence
package** and reports a post-run governance decision. It is source-neutral: it
reads a generic manifest + timeline contract and encodes no producer-specific
semantics.

This is **post-run governance validation before HTTP ingestion and runtime
decision APIs.** It inspects evidence after a run has finished; it performs no
runtime allow/review/block control.

## Package shape

A package is a directory containing at least:

- `manifest.json` — package metadata (`source`, `governance_mode`,
  `schema_version`, `run_id`, `generated_at`, and a `files` list).
- `timeline.json` — `schema_version`, `run_id`, and an `events` array.

## Public surface

Exposed from `ailuros.adapters.evidence_package`:

- `audit_evidence_package(package_dir) -> AuditResult`
- `audit_result_to_dict(result) -> dict`
- `audit_result_to_json(result) -> str`
- `audit_result_to_markdown(result) -> str`
- `validate_evidence_package_contract(package_dir) -> ValidationResult`

`AuditResult` and `AuditDecision` live in `ailuros.core.audit`. The generic,
source-neutral Markdown renderer lives in `ailuros.core.report`
(`render_audit_markdown`).

## Decision semantics

The audit emits exactly one `AuditDecision` with three values:

| Decision | Meaning |
|---|---|
| `pass` | Evidence is clean and contract-valid (no errors, no warnings). |
| `warn` | Evidence is valid but has tolerated anomalies (no errors, ≥1 warning). |
| `fail` | Evidence violates the package contract (≥1 error). |

`fail` always takes priority; warnings are still surfaced alongside a failure.

## Report rendering

`audit_result_to_markdown` produces a deterministic Markdown report with
Decision, Summary, Checks, Warnings, Errors, and Verdict sections. Output is
stable for a given result and contains no timestamps or environment-specific
data.

## CLI

```
ailuros evidence-audit <package-path> --format json|md [--out FILE]
```

The command audits the package on disk and prints (or writes) the report. It does
not change any existing CLI behavior.

## See also

- Contract: `docs/contracts/evidence-package-post-run-governance-v15.md`
- Demo: `docs/demo/evidence-package-v15-demo.md`
- Release: `docs/release/v1.5-post-run-governance.md`
