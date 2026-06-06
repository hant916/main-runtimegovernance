# v1.5 Demo — Auditing a Canonical Evidence Package

This demo audits a completed run's canonical evidence package and renders the
result as JSON and as Markdown.

v1.5 is **post-run governance validation before HTTP ingestion and runtime
decision APIs.** The audit runs after a run has finished and only reads the
evidence the run left behind. There is no allow/review/block runtime control.

## Input package

A canonical evidence package is a directory containing at least `manifest.json`
and `timeline.json`. A clean sample lives at:

```
tests/fixtures/evidence_package/valid-v15/
```

## JSON audit

```
ailuros evidence-audit tests/fixtures/evidence_package/valid-v15 --format json
```

This prints deterministic, sorted-key JSON describing the decision and context,
for example:

```json
{
  "decision": "pass",
  "errors": [],
  "events_count": 2,
  "governance_mode": "observe",
  "ok": true,
  "rules_evaluated": 2,
  "run_id": "run-sample-001",
  "schema_version": "ailuros.timeline.v0",
  "source": "sample-agent",
  "warnings": []
}
```

## Markdown audit

```
ailuros evidence-audit tests/fixtures/evidence_package/valid-v15 --format md
```

Example output:

```markdown
# Evidence Package Audit Report

## Decision

**PASS**

## Summary

| Field | Value |
|---|---|
| Decision | pass |
| OK | true |
| Governance mode | observe |
| Source | sample-agent |
| Schema version | ailuros.timeline.v0 |
| Run ID | run-sample-001 |
| Events | 2 |
| Rules evaluated | 2 |

## Checks

| Check | Status | Detail |
|---|---|---|
| Contract validation | pass | 0 error(s) |
| Anomalies | pass | 0 warning(s) |
| Rules evaluated | info | 2 |

## Warnings

None.

## Errors

None.

## Verdict

Evidence is clean and contract-valid.
```

Write the report to a file with `--out`:

```
ailuros evidence-audit tests/fixtures/evidence_package/valid-v15 --format md --out report.md
```

## Python API

```python
from ailuros.adapters.evidence_package import (
    audit_evidence_package,
    audit_result_to_json,
    audit_result_to_markdown,
)

result = audit_evidence_package("tests/fixtures/evidence_package/valid-v15")
print(audit_result_to_json(result))
print(audit_result_to_markdown(result))
```

## Known limitations

- Output formats are JSON and Markdown only. There is no HTML dashboard, PDF
  export, chart, web server, HTTP endpoint, or stored report history.
- The report renders only the fields the audit already produces; it adds no new
  validation or risk rules.
- The decision is post-run and advisory: it performs no runtime allow/review/block
  control and never returns a `BLOCKED` or `HUMAN_REVIEW` outcome.
