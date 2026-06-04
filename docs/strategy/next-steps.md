# Ailuros Next Steps

**Date:** 2026-06-04
**Source of truth:** local repository files and reproducible validation commands
only. EverRun execution traces, planner state, and hardening-pack history are **not**
treated as product truth (consistent with `sdd/current-state.md`).

This document records the analyzed development status and the planned next steps. It
sits alongside [roadmap.md](roadmap.md) and [phase1-readiness.md](phase1-readiness.md)
and is covered by the documentation-drift check.

## Current Status (measured)

Validation commands were run directly against the working tree:

| Check | Command | Result |
|---|---|---|
| Test suite | `python -m pytest tests -q` | 523 passed |
| Type check | `python -m mypy src` | no issues in 55 source files |
| Lint (whole repo) | `python -m ruff check .` | 7 errors (all in `examples/` + `scripts/`; `src/` is clean) |

Phase 0 (the v0.1 governance kernel) is complete. All nine roadmap Phase 0 items are
checked. The kernel surface includes runtime lifecycle, policy engine (12 operators),
decision resolver, SQLite storage (6 tables, 3 migrations), path validation, evaluation
and regression services, read-only replay/audit, the framework-neutral adapter contract
with `LocalCallableAdapter`, a read-only HTTP server (GET only), and the full CLI.

## Findings / Gaps

| # | Finding | Severity | Evidence |
|---|---|---|---|
| G1 | `ruff check .` fails with 7 errors | High — README and acceptance list `ruff check .` as a validation command, but it does not pass | `examples/hello.py:17` E501; `scripts/check_release_v010.py:3` F401; `scripts/check_repo_baseline.py:32,112` F541/B007 |
| G2 | Phase 1 (Clarify evidence ingestion) has zero code | Medium — next mainline; documented only | `phase1-readiness.md` three `[ ]` deferred items |
| G3 | `ailuros.sqlite` (348 KB demo artifact) sits at repo root in the working tree | Low — already untracked; `.gitignore` `*.sqlite` covers it. Verified not in `git ls-files`. | `git ls-files \| grep sqlite` lists only source files |
| G4 | Release status is still `release-candidate` | Low — kernel is stable, can be finalized | `docs/release/v0.1.0-acceptance.md` |
| G5 | EverRun planner/coder backends fall back | None for product — tooling issue, not product truth | execution-report `planner_unavailable` |

## Plan

### Phase P0 — Baseline Cleanup (0.5–1 day)

Goal: make `ruff check .`, `pytest`, and `mypy` all green, and finalize v0.1.0.

v0.1.0 documentation is complete and the release is documented as finalized
(`docs/release/v0.1.0-finalization.md` status: finalized). The remaining P0 gap is
the ruff lint cleanup.

| Task | Action | Acceptance evidence |
|---|---|---|
| P0-1 Fix ruff | Wrap `examples/hello.py:17`; remove unused `import re` in `scripts/check_release_v010.py`; drop placeholder-less `f` in `scripts/check_repo_baseline.py:32`; replace unused `label` loop var | `ruff check .` → all checks passed |
| P0-2 Repo hygiene | Verified `ailuros.sqlite` is already untracked (`.gitignore` `*.sqlite` in effect); no action needed | `git ls-files \| grep sqlite` lists only source files |

### Phase P0.5 — Backend-Health Assessment (before Phase 1)

Before Phase 1 evidence-model work begins, an EverRun backend-health assessment is
recommended. The most recent Ailuros run was accepted-with-warnings:
`planner_unavailable`, `judge_not_invoked`, `deterministic_fallback_used`,
`coder_backend_warning`, and `tool_schema_error` were reported. Code validation
passed (523 tests) but governance participation was incomplete.

See [ailuros-run-reconciliation.md](ailuros-run-reconciliation.md) for the full
reconciliation report.

### Phase P1 — Clarify Evidence Integration (pack-by-pack)

Strictly evidence-only: unidirectional evidence in, no HTTP write API, no browser
reverse control, no Clarify concept in `src/ailuros/`. The kernel recognizes only the
generic five-field contract (`version`/`run_id`/`event_type`/`payload`/`timestamp`)
from `docs/contracts/phase1-evidence-only-contract.md`.

Phase 1 evidence implementation (0070-0072) is already complete — the code, tests,
and exports exist in the repository. The remaining work is formal v0.2.0 release
verification. The roadmap (`docs/strategy/evidence-roadmap-v0.2.md`) is the
authoritative pack-by-pack plan; this section provides a summary.

| Pack | Scope | Status |
|---|---|---|
| 0070 Contract verify | EvidenceRecord model contract (five fields, opaque payload, free-form event_type) | COMPLETE — `src/ailuros/models/evidence.py` + `tests/test_evidence_contract.py` (147 lines) |
| 0071 Ingest | `ingest_evidence(run_id, record)` stores external JSON evidence as an `EVIDENCE` timeline event | COMPLETE — `src/ailuros/evidence/ingest.py` + `tests/test_evidence_ingest.py` (165 lines) |
| 0072 Export | `export_evidence()` + CLI — export stored evidence as JSON/JSONL | COMPLETE — `src/ailuros/evidence/export.py` + `tests/test_evidence_export.py` (218 lines) |
| 0073 Release verify | Run v0.2.0 smoke checks, create readiness doc, flip acceptance status | NEXT PACK — requires `scripts/check_release_v020.py` and `tests/test_release_v020.py` |

No new core architecture is introduced — within the `v0.1.0-acceptance.md` non-goal
boundary. Each pack depends on the prior pack passing.

## Execution Order

```
P0 (ruff cleanup) ──► 0070–0072 (already complete) ──► 0073 v0.2.0 release verify ──► later packs (Phase 2+)
```
