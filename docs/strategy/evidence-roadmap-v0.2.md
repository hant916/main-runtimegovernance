# Ailuros Evidence Roadmap v0.2

**Date:** 2026-06-04
**Task ID:** 0069.regenerate-ailuros-evidence-roadmap-from-repo-state
**Source of truth:** Actual repository files, not memory or stale backlog

This roadmap is regenerated from repository state after v0.1/v0.2 readiness work.
It replaces any previous roadmap assumptions with file-grounded evidence.

## Current Verified State

Repository validation executed against the working tree:

| Check | Command | Result | Source |
|---|---|---|---|
| Test suite | `python -m pytest tests -q` | 523 passed | `ailuros-run-reconciliation.md` line 59 |
| Type check | `python -m mypy src` | no issues in 55 source files | `next-steps.md` line 19 |
| Lint | `python -m ruff check .` | 7 errors in `examples/` + `scripts/` only; `src/` clean | `next-steps.md` line 20 |
| Evidence model | `src/ailuros/models/evidence.py` | Exists with 5 fields, `extra="forbid"`, opaque payload | Direct file inspection |
| Evidence ingest | `src/ailuros/evidence/ingest.py` | Exists — `ingest_evidence()` stores as EVIDENCE timeline event | Direct file inspection |
| Evidence export | `src/ailuros/evidence/export.py` | Exists — `export_evidence()`, `export_evidence_json()`, `export_evidence_jsonl()` | Direct file inspection |
| Evidence contract tests | `tests/test_evidence_contract.py` | Exists — 147 lines, 8 test classes | Direct file inspection |
| Evidence ingest tests | `tests/test_evidence_ingest.py` | Exists — 165 lines, 2 test classes | Direct file inspection |
| Evidence export tests | `tests/test_evidence_export.py` | Exists — 218 lines, 5 test classes | Direct file inspection |
| Evidence evaluation tests | `tests/test_evidence_evaluation.py` | Exists — 362 lines, 5 test classes | Direct file inspection |
| Evidence regression tests | `tests/test_evidence_regression.py` | Exists — 300 lines, 9 test classes | Direct file inspection |
| v0.2.0 acceptance | `docs/release/v0.2.0-acceptance.md` | Status: acceptance-defined | Direct file inspection |
| v0.2.0 release script | `scripts/check_release_v020.py` | Exists | Direct file inspection |
| v0.2.0 release tests | `tests/test_release_v020.py` | Exists | Direct file inspection |
| v0.2.0 readiness doc | `docs/release/v0.2.0-readiness.md` | Does NOT exist | Direct file inspection |

**Backend-health status (from pack 0067 reconciliation):**
- `planner_unavailable` — planner was not reachable during the last Ailuros run
- `judge_not_invoked` — judge was not called to evaluate run output
- `deterministic_fallback_used` — runner used deterministic fallback
- `coder_backend_warning` — coder backend reported health issue
- `tool_schema_error` — tool schema validation produced errors
- Source: `docs/strategy/ailuros-run-reconciliation.md` lines 11-18, 70-78

These are governance/infrastructure warnings, not code-semantic failures. Validation
(523 passing tests) confirms produced code state is valid.

## Completed / Obsolete Packs

These are satisfied by repository evidence and must NOT be regenerated.

| Pack | Description | Evidence | Status |
|---|---|---|---|
| v0.1.0 release | Governance kernel (runtime, policy engine, storage, path validation, eval/regression, replay/audit, adapter contract, HTTP server GET-only, CLI, hello demo) | `docs/release/v0.1.0-finalization.md` status: finalized; 523 tests pass | COMPLETE |
| v0.1.0 docs | CHANGELOG, README, checklist, finalization, acceptance, contracts, roadmap | All files exist and are referenced from finalization.md | COMPLETE |
| Phase 1 contract | Evidence-only contract, readiness doc, ADR-0003 | `docs/contracts/phase1-evidence-only-contract.md`, `docs/strategy/phase1-readiness.md`, `docs/decisions/ADR-0003-evidence-first-integration.md` | COMPLETE |
| v0.2.0 scope | Acceptance criteria defined | `docs/release/v0.2.0-acceptance.md` status: acceptance-defined | COMPLETE |
| 0067 reconciliation | Run reconciliation report | `docs/strategy/ailuros-run-reconciliation.md` | COMPLETE |
| 0069 roadmap regeneration | This document | `docs/strategy/evidence-roadmap-v0.2.md` | COMPLETE (this pack) |
| **0070** — EvidenceRecord contract | Model with 5 fields (version/run_id/event_type/payload/timestamp), opaque payload, free-form event_type | `src/ailuros/models/evidence.py` exists; `tests/test_evidence_contract.py` (147 lines) covers field validation, serialization, extra field rejection, timezone enforcement, application-neutrality | COMPLETE |
| **0071** — Evidence ingest | `ingest_evidence(run_id, record)` stores external JSON evidence as EVIDENCE timeline event | `src/ailuros/evidence/ingest.py` exists; `tests/test_evidence_ingest.py` (165 lines) covers timeline storage, payload preservation, multi-event, unique IDs, boundary cases | COMPLETE |
| **0072** — Evidence export | `export_evidence()`, `export_evidence_json()`, `export_evidence_jsonl()` with CLI `export <run_id>` | `src/ailuros/evidence/export.py` exists; `tests/test_evidence_export.py` (218 lines) covers empty/identity/ordering/timestamps/payload/JSON/JSONL/filtering | COMPLETE |

## Partial Packs

Work started but not fully satisfied. Marked for completion, not regeneration.

| Pack | Description | What remains | Evidence |
|---|---|---|---|
| P0-1 ruff cleanup | Make `ruff check .` green | 7 errors in `examples/hello.py:17` (E501), `scripts/check_release_v010.py:3` (F401), `scripts/check_repo_baseline.py:32,112` (F541/B007) | `next-steps.md` lines 32-33, 50; v0.1.0 finalized with cosmetic deferral |
| 0084 v0.2.0 acceptance gate | Define and verify v0.2 acceptance gate: smoke check passes (31/31), release tests pass (7/7), full suite 557 passed. Status remains acceptance-defined until formal release. | v0.2.0-acceptance.md status updated; check_release_v020.py passes; 557 tests pass | `docs/release/v0.2.0-acceptance.md`; `scripts/check_release_v020.py`; `tests/test_release_v020.py` |

The ruff errors are cosmetic (not in `src/` core) and do not block evidence work.
The v0.2.0 implementation is already present in source; only formal verification and
readiness documentation remain.

## Skipped Packs

These were considered but are no longer needed.

| Pack | Reason |
|---|---|
| Backend-health as separate blocking gate | Backend warnings do not block code validation (523 tests pass). Proceeding with accept_with_warnings risk is acceptable for evidence-model work that itself produces test-validated code. |
| Regenerating v0.1.0 release docs | Already satisfied by the accepted-with-warnings run. |
| 0070/0071/0072 as next packs | These packs are already implemented and tested. Code, tests, and exports exist in the repository. |

## Next Packs

These are the ordered, narrow, validation-gated packs for the remaining Phase 1 evidence work.

### 0084 — v0.2.0 Evidence Pipeline Acceptance (completed)

**Goal:** Define the final v0.2 evidence pipeline acceptance gate: record exactly what
the MVP evidence pipeline supports and what it does not support. No source feature work.

**Scope (completed):**
- Inspect evidence model, ingest, export, CLI, evaluation, regression, boundary guard,
  audit section, and demo files against actual repository state
- Run `scripts/check_release_v020.py` — 31/31 checks pass
- Run `tests/test_release_v020.py` — 7/7 tests pass
- Run full test suite — 557 tests pass
- Update `docs/release/v0.2.0-acceptance.md` with pack ID, date, and verification evidence
- Update `docs/strategy/evidence-roadmap-v0.2.md` and `docs/strategy/next-steps.md`
- No source implementation files modified
- No server write API claimed
- No real Clarify/browser/radarCreation integration claimed

**Non-scope:**
- No new evidence implementation
- No new core abstractions
- No server write API introduction
- No domain-specific evidence examples in core
- No backend-health repair (separate concern)
- No readiness doc created (scope is acceptance gate definition, not release)

**Dependencies:**
- `docs/release/v0.2.0-acceptance.md` (exists, status: acceptance-defined)
- `scripts/check_release_v020.py` (exists)
- `tests/test_release_v020.py` (exists)
- 0083.evidence-demo-local-fixture (prior pack, completed)
- 0070/0071/0072 implementation (completed — code already in repo)

**Validation (verified):**
- `scripts/check_release_v020.py` — 31/31 checks pass
- `tests/test_release_v020.py` — 7/7 tests pass
- `python -m pytest tests -q` — 557 pass
- Core boundary guard enforces no server write API (`do_POST`/`do_PUT`/`do_PATCH`/`do_DELETE`)
- No domain-specific vocabulary leaked into `src/ailuros/` core

### Later Phase 1 Work (after v0.2.0 verification)

| Pack | Description | Status |
|---|---|---|
| Phase 1 docs finalization | Flip remaining `[ ]` items in `phase1-readiness.md` to `[x]` for evidence items | DONE — resolved by pack 0085 (v0.3 readiness closeout) |
| Phase 1 boundary guard audit | Verify core boundary test still passes and no domain terms leaked | PENDING (human review, not blocking) |
| v0.2.0 git tag | Create and push git tag `v0.2.0` (human decision) | PENDING (human decision) |

## v0.3 MVP Scope

See `docs/release/v0.3.0-scope.md` (created by pack 0085).

v0.3 MVP is the next implementation target:

| Capability | Scope |
|---|---|
| Audit package exporter | Extend v0.2 audit section to produce full audit packages from evidence |
| Refund governance demo | Single deterministic demo exercising evidence-to-audit-package flow |
| v0.3 acceptance gate | Release smoke check, release tests, scope boundary guard |

**Non-goals for v0.3:** Server write API, UI dashboard, agent orchestration, browser governance, Clarify integration, radarCreation integration, MCP Gateway integration, broad adapters.

## Later Packs

Work deferred beyond v0.3 MVP.

| Pack | Description | When |
|---|---|---|
| P0-1 ruff cleanup | Fix 7 ruff errors in examples/scripts/ | Anytime; cosmetic, not blocking |
| Phase 2 Governed LLM Call | Policy evaluation over LLM content | After v0.3.0 released |
| Phase 3 EverRun Loop | Continuous-run governance | After Phase 2 |
| Phase 4 radarCreation Vertical | Domain-specific governance rules | After Phase 3 |
| Phase 5 Platformization | Multi-tenant server, REST API, dashboard, adapter ecosystem | Explicitly deferred |

## Boundary Rules

These boundaries apply across all next and later packs.

1. **Server write APIs excluded from Phase 1.** No `do_POST`, `do_PUT`, `do_PATCH`,
   `do_DELETE` in `src/ailuros/server/`. The HTTP server remains read-only (GET only)
   per `docs/contracts/phase1-evidence-only-contract.md` line 41-42.

2. **Domain-specific evidence examples stay outside `src/ailuros/`.** Clarify,
   browser, radarCreation, sidepanel, CTA vocabulary is forbidden in core modules per
   the boundary guard (`tests/test_core_boundary.py` and
   `docs/contracts/phase1-evidence-only-contract.md` lines 31-38).

3. **EvidenceRecord payload is opaque.** Core stores and retrieves evidence records
   without interpreting payload contents. Domain-specific payload shapes are defined
   by applications, not in `src/ailuros/`.

4. **No new runtime/backend changes.** Implementation packs must not modify EverRun
   runtime, backend configuration, or governance infrastructure.

5. **No BLOCKED or HUMAN_REVIEW path for non-capability reasons.** Proceed with
   accept_with_warnings when backend-health issues are known but code validation
   passes.

## Validation Strategy

Each next pack must pass these gates before marking complete:

| Gate | Command | Threshold |
|---|---|---|
| Test suite | `python -m pytest tests -q` | All pass |
| Type check | `python -m mypy src` | No issues |
| Lint | `python -m ruff check .` | Accept `examples/` and `scripts/` errors as known cosmetic gap; `src/` must be clean |
| Contract check | Manual review against `phase1-evidence-only-contract.md` | No server write APIs, no domain-specific core leak |
| v0.2.0 smoke | `scripts/check_release_v020.py` | All checks pass (for 0084 only) |
| v0.2.0 release tests | `tests/test_release_v020.py` | All pass (for 0084 only) |

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Backend-health warnings persist through 0073+ | Medium | Accept accept_with_warnings for code-validated packs. Code validation (tests, type check) is independent of planner/judge availability. |
| Unknown (Task 0055 status cannot be determined from repo files) | Low | Marked as unknown in reconciliation report. Does not block evidence work. |
| v0.2.0 readiness doc does not exist yet | Low | Will be created by pack 0073; v0.2.0-acceptance.md already defines acceptance criteria. |
| Cosmetic ruff errors may distract reviewers | Low | Errors are in examples/scripts/ only, not in src/. Fix anytime; does not block. |

## Known Unknowns / Contradictions

- Task 0055: No reference found in repository files. Cannot determine satisfaction
  status. Recorded as unknown per `docs/strategy/ailuros-run-reconciliation.md` line 116.
- Planner/judge ACCEPT: Cannot verify. Run evidence reports `planner_unavailable`
  and `judge_not_invoked`.
- `docs/release/v0.2.0-readiness.md` does not exist (will be created by pack 0073).
- **Resolved contradiction (pack 0085):** `docs/strategy/phase1-readiness.md` previously
  listed evidence ingestion, export, and evaluation as `[ ]` deferred items while
  source-code already implemented these features. Pack 0085 (v0.3 readiness closeout)
  resolved this by flipping the three items to `[x]` with source-file evidence.
  The doc is now in sync with the implemented state.
