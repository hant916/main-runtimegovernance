# Ailuros v1.5 Closure Report

**Status:** Accepted

**Date:** 2026-06-09

**Task ID:** 0003.v150-closure-report-and-doc-alignment

## Scope

v1.5 delivers **offline post-run governance validation**: load a canonical evidence
package, validate its contract, run a deterministic audit, and render a pass/warn/fail
decision in JSON or Markdown. The capability is post-run only and does not see,
intercept, or control live execution.

## Accepted Capabilities

| Pack | Capability | Evidence |
|---|---|---|
| C-008 | Clarify evidence handoff | `scripts/validate_clarify_handoff.py` — `validate_clarify_timeline` |
| A-005R1 | Evidence package loader | `src/ailuros/adapters/evidence_package/loader.py` — `load_evidence_package` |
| A-005R2 | Timeline contract validator | `src/ailuros/adapters/evidence_package/validator.py` — `validate_evidence_package_contract` |
| A-005R3 | Minimal governance decision | `src/ailuros/adapters/evidence_package/audit.py` — `audit_evidence_package` |
| A-006R | Markdown audit report | `src/ailuros/adapters/evidence_package/markdown_report.py` — `audit_result_to_markdown` |

Public API surface (exported from `ailuros.adapters.evidence_package`):
`audit_evidence_package`, `load_evidence_package`, `validate_evidence_package_contract`,
`audit_result_to_markdown`, `audit_result_to_dict`, `audit_result_to_json`.

Core types: `AuditResult`, `AuditDecision` (`src/ailuros/core/audit.py`),
`render_audit_markdown` (`src/ailuros/core/report.py`).

CLI: `ailuros evidence-audit <package-path> --format json|md [--out <file>]`.

## Validation Commands

```bash
python scripts/check_release_v150.py
python -m pytest tests -q
```

## Remaining Non-Goals

v1.5 does **not** introduce:

- Runtime blocking or live tool interception.
- HTTP ingestion API or server endpoints.
- Allow/warn/review/block decision surface (v2.5+ boundary).
- UI dashboard, PDF export, or web server.
- Complex policy DSL or multi-agent registry.
- Production Clarify/EverRun/radarCreation integrations.
- Marketplace or enterprise permission model.
- EverRun dogfood or `dogfood/` artifact production.

## Proof Boundaries

- The release checker (`scripts/check_release_v150.py`) is the product-level proof.
- All five v1.5 execution packs have corresponding source modules, tests, and fixtures.
- C-008R1 handoff validation runs as a subprocess and must pass.
- Tests guarding v1.5-specific modules:
  `test_evidence_package_loader.py`, `test_evidence_package_contract_validator.py`,
  `test_evidence_package_markdown_report.py`, `test_post_run_governance_decision.py`.
- Test fixture: `tests/fixtures/evidence_package/valid-v15/` (manifest.json + timeline.json).
- Non-goals are verified by the checker scanning `evidence_package/__init__.py` for
  forbidden tokens (`http`, `block`, `server`).

## Related

- Release doc: `docs/release/v1.5-post-run-governance.md`
- Contract: `docs/contracts/evidence-package-post-run-governance-v15.md`
- Demo: `docs/demo/evidence-package-v15-demo.md`
- Roadmap: `docs/strategy/roadmap.md` (v1.5 section)
- README: `README.md`
