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

### Phase P1 — Clarify Evidence Integration (3–5 days)

Strictly evidence-only: unidirectional evidence in, no HTTP write API, no browser
reverse control, no Clarify concept in `src/ailuros/`. The kernel recognizes only the
generic five-field contract (`version`/`run_id`/`event_type`/`payload`/`timestamp`)
from `docs/contracts/phase1-evidence-only-contract.md`.

| Task | Module | Design | Acceptance evidence |
|---|---|---|---|
| P1-1 Ingest | `src/ailuros/evidence/ingest.py` | `ingest_evidence(run_id, record)` stores external JSON evidence as an `EVIDENCE` timeline event; validates only the generic five-field contract, never payload shape | `tests/test_evidence_ingest.py`; visible via `replay` |
| P1-2 Export | `src/ailuros/evidence/export.py` + CLI `export <run_id>` | Export stored evidence timeline as JSON/JSONL for external analysis | `tests/test_evidence_export.py`; round-trip consistent |
| P1-3 Eval | reuse `EvaluationService` | Run golden cases against evidence timelines (non-realtime) | new `examples/evaluation/evidence_*.json` |
| P1-4 Regression | reuse `RegressionService` | Re-evaluate evidence sets as policy changes | `tests/test_evidence_regression.py` |
| P1-5 Boundary guard | `tests/test_core_boundary.py` | Static assert `src/ailuros/` contains no `browser`/`clarify`/`cta`/`sidepanel`; no HTTP write method | guard test passes |
| P1-6 Docs sync | flip `phase1-readiness.md` items to `[x]`; add dogfood doc | documentation-drift check passes |

P1-3/P1-4 reuse the existing `EvaluationService`/`RegressionService`; evidence is just a
new event type, so no new core architecture is introduced — within the
`v0.1.0-acceptance.md` non-goal boundary.

## Execution Order

```
P0 (ruff cleanup) ──► P0.5 (backend-health assessment) ──► P1-1 ingest ──► P1-2 export ──► P1-3/4 eval+regression ──► P1-5/6 guard+docs
```
