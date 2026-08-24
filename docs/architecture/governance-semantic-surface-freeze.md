# Governance Semantic Surface Freeze

**Status:** Frozen (evidence-backed as of 2026-08-24)
**Scope:** Ailuros governance semantic surface — dimensions, transitions, lifecycle,
outcomes, authority/approval/budget, scope, validation, signals, coverage,
provenance, temporal attribution, and regression delta.
**Evidence basis:** Packs 8065–8068, EverRun dogfood runs
(`run-20260824-004751`, `run-20260824-011708`), and the full clean validation
suite (1436 passed on 2026-08-24).

This record freezes the governance semantic surface *proven by implemented code
and tests*, not by pack titles. It defines what may continue during the freeze
and what requires new production evidence before it can enter the roadmap.

---

## 1. Inventory of Implemented Canonical Semantics

Source of truth is current code + tests. Each semantic surface lists its owning
module, canonical symbols, and locking tests. No pack-only concept with no code
evidence is listed as implemented surface.

| Semantic surface | Owner (module) | Canonical symbols | Locking tests |
|---|---|---|---|
| Identity | `core/execution.py`, `models/` | `ExecutionProjection.run_id/source/schema_version`, `EvidenceRef.event_id`, `DecisionSummary.scope_ref`, timezone-aware `datetime` | `test_ailuros_timeline_schema.py`, `test_audit_package_validator.py`, `test_evidence_export.py::test_export_preserves_event_identity` |
| Lifecycle | `core/execution.py`, `projection.py` | `Lifecycle` (running/completed/failed/unknown); derived from `run_started`/`run_completed`/`run_failed` in `build_execution_projection` | `test_projection_lifecycle.py` |
| Outcomes (native) | `projection.py:326` | `derive_native_outcome` → `Outcome` (success/partial/blocked/review_required/failed/unknown); decision priority block=4, require_review=3; falls back to lifecycle | `test_outcome_precedence.py`, `test_projection_lifecycle.py` |
| Outcomes (governed) | `projection.py:348`, `core/execution.py` | `_governed_outcome`, `GovernedOutcome` (clean_success/degraded_success/review_required/failed/unknown); precedence FAILED > REVIEW_REQUIRED > UNKNOWN > DEGRADED > CLEAN; never promotes unknown to clean | `test_governed_outcome.py` (aggregation tests) |
| Authority | `core/execution.py:192`, `projection.py` | `AuthorityRecord`, `AuthorityState` (authorized/violation/unknown), `_normalize_authority_state` | `test_authority_governance.py` |
| Approval | `core/execution.py:138`, `projection.py` | `ApprovalRecord`, `ApprovalState` (approved/denied/unknown) | `test_approval_governance.py` |
| Budget | `core/execution.py:177`, `projection.py` | `BudgetRecord`, `_budget_exceeded`, `_budget_unknown_required`, `_BUDGET_EXCEEDED_STATUSES` | `test_budget_governance.py` |
| Scope | `core/execution.py`, `projection.py`, `signals.py` | `Scope` (clean/violated/unknown), `scope_ref` propagated load→ingest→projection→signals | `test_projection_decisions.py` (external-wrapper/scope tests), `test_governance_signals.py` |
| Validation | `core/execution.py`, `projection.py:83` | `Validation` (passed/failed/partial/not_run/unknown), `_resolve_validation` | `test_projection_runtime_facts.py` |
| Signals | `signals.py` | `GovernanceSignal`, `derive_signals`, per-`(scope_ref, projected_domain)` `evidence_inconsistency` rule | `test_governance_signals.py` |
| Coverage | `core/execution.py`, `projection.py:302` | `GovernanceCoverage`, `CoverageState` (evaluated/unknown/not_applicable), `_derive_governance_coverage` | `test_authority_governance.py`, `test_approval_governance.py`, `test_budget_governance.py` |
| Provenance | `core/execution.py`, `projection.py:105` | `EvidenceRef`, `GovernanceContext.source_pointers`, `evidence_refs` retained through decisions and governed result | `test_governance_context_projection.py`, `test_governed_outcome.py::test_run_report_governed_outcome_reasons_carry_evidence_refs` |
| Temporal attribution | `core/execution.py` (field_validator `require_timezone`) | `started_at`, `completed_at` timezone-aware invariant | `test_temporal_governance.py` |
| Regression delta | `regression/governance_delta.py` | `GovernanceDimension` (12), `GovernanceTransition` (5), `compare_governance_projections` | `test_regression.py` |

### 1.1 Regression dimensions (exactly 12)

The `GovernanceDimension` enum (`regression/governance_delta.py:18`) and the
derived `_DIMENSION_ORDER: tuple[GovernanceDimension, ...] = tuple(GovernanceDimension)`
(`regression/governance_delta.py:58`) are the single authoritative dimension set.

| Dimension | Rank semantics |
|---|---|
| `native_outcome` | `derive_native_outcome` hierarchy (success 4, partial 3, review_required 2, blocked 1, failed 1) |
| `governed_outcome` | post-run governed classification |
| `validation` | passed 4 / partial 3 / not_run 2 / failed 1 |
| `scope` | clean 2 / violated 1 |
| `authority` | authorized 2 / violation 1 |
| `approval` | approved 2 / denied 1 |
| `budget` | within_budget 2 / exceeded 1 (normalized via `_budget_state`) |
| `authority_coverage` | evaluated |
| `approval_coverage` | evaluated |
| `budget_coverage` | evaluated |
| `validation_coverage` | evaluated |
| `scope_coverage` | evaluated |

### 1.2 Regression transitions (exactly 5)

`GovernanceTransition` (`regression/governance_delta.py:33`):
`improved`, `regressed`, `unchanged`, `unknown`, `incomparable`.

**Source neutrality:** `_facts()` (`governance_delta.py:119`) reads only projection
facts and coverage — never `source` or producer identity; run_id is output
metadata only. Locked by `tests/test_regression.py`
`test_governance_delta_ignores_source_identity_variation`,
`test_governance_delta_ignores_run_id_variation`, and
`test_governance_delta_detects_improvement_and_ignores_producer_identity`.
Canonical-parity evidence (8073): both canonical fixtures — the EverRun-derived
`fixtures/runtime-evidence/everrun-postfix-minimal` and the generic MCP-style
`fixtures/runtime-evidence/second-producer` — are driven through the identical
shared pipeline (validate → load → ingest → rebuild → report) and through the
regression read-model with only the source label relabeled; the full 12-dimension
transition matrix is unchanged. Locked by `test_second_producer_conformance.py`
(`test_everrun_postfix_minimal_and_second_producer_run_identical_shared_pipeline`,
`test_projection_source_label_is_inert_to_regression_interpretation`,
`test_unknown_events_survive_without_promoting_clean_across_canonical_fixtures`)
and `test_regression.py`
(`test_canonical_everrun_and_second_producer_regression_is_source_label_inert`,
`test_canonical_fixture_self_delta_under_relabel_is_identity`).

---

## 2. Convergence Status (8065–8068)

Classification categories used below: **fixed**, **open**, **expected-unknown**
(missing evidence, never promoted to clean), **insufficient-evidence** (a claim
that cannot be backed by the delivered artifact).

| Pack | Result | Classification | Evidence |
|---|---|---|---|
| 8065 — Direct producer acceptance | Post-fix raw export (`run-20260824-004751`, 38 events) is directly consumable: `evidence-audit` ok=true/warn, import `created`, rebuild completes with `lifecycle=running`, `validation=passed`, `scope=clean` | **Fixed** (structural conformance); remaining unknowns are expected-unknown | `docs/operations/everrun-dogfood.md` §Direct Raw Acceptance — Post-Fix; `docs/dogfood/everrun-history-baseline.md` §8065 |
| 8066 — Semantic projection after export fix | Source-proven terminal/decision/validation/scope semantics project into canonical fields source-neutrally; missing evidence stays conservative | **Fixed** (verification only; no production change) | `everrun-dogfood.md` §8066; `test_projection_lifecycle.py`, `test_projection_decisions.py`, `test_projection_runtime_facts.py` |
| 8067 — Real governance regression proof | Real pair (`run-20260824-004751` → `run-20260824-011708`) transition matrix matches documented semantics; no comparator defect | **Fixed** (comparator); one **open** projection-side gap recorded | `everrun-dogfood.md` §8067; `test_regression.py::test_governance_delta_real_everrun_pair_transition_matrix` |
| 8068 — Source-neutrality lock | Tests lock source- and run-id-neutrality; comparator reads no producer identity | **Fixed** (behavior locked by tests); **insufficient-evidence** for the pack's `production_path: true` contract claim (deliverable was a behavioral test-lock, not a production-path proof) | `test_regression.py` source/run-id identity tests; pack record `sdd/task-dir/8068.*.todo.json` remains `.todo` (open scheduling) |

### 2.1 Fixed / open / expected-unknown / insufficient-evidence summary

- **Fixed (5):** 8065 structural conformance; 8066 projection semantics;
  8067 comparator matrix; 8068 source-neutrality behavior; 8064-era
  cross-scope false-positive class (recorded in
  `everrun-history-baseline.md` §8064).
- **Open (2, non-blocking, out of this pack's scope):**
  - 8067 event-ordering gap: exporter writes terminal `run_completed` before
    `run_started`, so `build_execution_projection` derives `lifecycle=running`
    despite the `success` fact being present. Fix belongs to
    `src/ailuros/projection.py`; recorded as a future candidate (per the pack,
    source projections are not mutated).
  - 8068 scheduling record: the pack file is still `.todo.json` although the
    source-neutrality tests are committed and green — a process/bookkeeping gap,
    not a behavior gap (open issue
    `planner_proposed_accept_and_no_blocking_rule_triggered`).
- **Expected-unknown (2):** 34 unrecognized event types (`backend.*`,
  `projection.*`, `session.fallback`, …) are mapping-missing, preserved as
  `source_preserved_unknown`, never inferred clean; authority/approval/budget
  coverage is evidence-missing in the real exports and stays `unknown`.
- **Insufficient-evidence (1):** 8068's `production_path: true` contract claim
  (deliverable was a test lock). Not a blocking defect: the source-neutral
  behavior itself is mechanically locked.

**Convergence claim:** bounded convergence for the 8065–8068 dogfood surface is
supported — no unresolved *blocking* cross-boundary defect was exposed, so the
freeze may proceed. This is not a claim of universal convergence: expected-unknown
and mapping-missing surfaces remain, and no new top-level primitive is asserted.

---

## 3. Freeze Rules

### 3.1 Allowed during freeze (convergence work)

- Producer conformance fixes (consumer-side, contract-preserving).
- Projection correctness (event ordering, missing-evidence handling) — fixes
  existing semantics, not new semantics.
- Evidence attribution and conflict correctness.
- Regression correctness (comparator determinism/performance).
- Report quality and dogfood tooling.
- Test coverage expansion for existing dimensions and transitions.
- Documentation improvements (this pack's scope).

### 3.2 Disallowed without new production evidence

- New top-level governance primitive.
- New regression dimension (beyond the 12) or new transition (beyond the 5).
- Workflow/state-engine behavior or execution orchestration.
- Producer-specific semantics or new comparability framework.
- New BLOCKED / HUMAN_REVIEW runtime path.

### 3.3 Roadmap gate

A new top-level governance primitive may enter the committed roadmap **only**
after: (a) new production evidence exists (a real package / dogfood finding that
demonstrates the missing capability), and (b) a governance pack that carries that
evidence and proves the need. A pack title alone is not evidence.

---

## 4. Clean Baseline Validation (T4)

Run on 2026-08-24 without changing any test expectations:

```
python -m pytest tests -q
```

Result: **1436 passed** in ~85s, 1 environmental warning (pytest cache path
creation on Windows: WinError 183 — unrelated to the suite). No failures, no
test modifications.

---

## 5. Frozen Elements

The following are frozen and may not be modified without a new governance pack:

- The 12 governance dimensions and their rank tables (`GovernanceDimension`,
  `_DIMENSION_ORDER`, `_ranks_for`).
- The 5 transition types and their semantics (`GovernanceTransition`,
  `_transition`).
- `compare_governance_projections` signature and source-neutrality contract.
- Projection-derived semantics: lifecycle/outcome/validation/scope/coverage
  derive from canonical `event_type`/`payload` fields only; free-text
  `payload.outcome` is deliberately ignored for terminal-state derivation.
- The evidence package contract (`ailuros.timeline.v1`): manifest with
  `files[].name`, timeline as object with `events` array.
- Governance ownership maps: `canonical-governance-surface.md`,
  `governance-boundary.md`, and `governed-execution-scope-v1.md`.

---

## 6. Remaining Gaps (Evidence-Backed)

| Gap | Status | Evidence |
|---|---|---|
| 8068 pack contract/goal mismatch (`production_path: true` vs test-lock) | Insufficient-evidence | Pack record `8068.*.todo.json`; delivered tests only |
| 8068 scheduling record still `.todo` | Open (process) | `sdd/task-dir/8068.lock-source-neutral-regression-against-producer-coupling.todo.json` |
| 8067 terminal-event ordering gap | Open (non-blocking) | `everrun-dogfood.md` §8067 |
| 34 unknown event types in exports | Expected-unknown (mapping-missing) | `everrun-dogfood.md` §8065 post-fix; `run-20260824-004751` audit warnings |
| Authority/approval/budget coverage in real exports | Expected-unknown (evidence-missing) | `everrun-dogfood.md` §8065 post-fix T4 |
| Multi-run longitudinal regression | Not yet built | No cross-run delta mechanism; `everrun-dogfood.md` §Optional Repeated-Run Governance Delta is post-run comparison only |

---

## 7. Freeze Enforcement

- New dimension → requires a governance pack with production-path proof.
- New transition → requires evidence that the existing 5 are insufficient.
- New top-level primitive → roadmap gate in §3.3 applies.
- Module ownership changes → require `canonical-governance-surface.md` update.
- Evidence package format changes → require a `timeline.v1` schema version bump.
