# Governance Production Baseline

**Status:** Frozen (production-backed, pack 8082, 2026-08-24)
**Scope:** The Ailuros governance baseline proven by production evidence across
packs 8065–8081. This record freezes what is supported by accepted real or
production-derived evidence, classifies every canonical surface area, records
open gaps without inventing fixes, and states the post-8082 next-step rule.
**Evidence basis:** Pack records (`.done.json` checkpoints 8065–8081 in
`sdd/task-dir`), `docs/operations/everrun-dogfood.md`,
`docs/dogfood/everrun-history-baseline.md`,
`docs/architecture/governance-semantic-surface-freeze.md`,
`docs/architecture/governance-release-readiness-2026-08.md`, the committed
fixtures and golden case, and the full clean validation suite (1482 passed on
2026-08-24).
**Relationship to prior records:** extends the 8069 semantic-surface freeze and
the 8075 release-readiness checkpoint with the 8076–8081 durability/evidence
line (deterministic replay, import/rebuild idempotency, unknown-event
preservation, scope-conflict controls, producer compatibility matrix, regression
corpus). This record is the consolidating baseline; it changes no code or test.

---

## 1. T1 — Predecessor evidence verification (8065–8081)

Every pack below was verified against committed code/tests/fixtures on disk, not
by pack title. A pack is **verified** when its claimed artifact exists, is
referenced by a real test/function, and the full suite passes. No required
predecessor remains `todo` due to a blocking correctness defect; the single
non-`.done` record (8068) is a scheduling/process gap with mechanically locked
behavior (see §3).

| Pack | Capability | Evidence verified | T1 status |
|---|---|---|---|
| 8065 — Direct raw acceptance | Raw EverRun `evidence/` enters audit → import → rebuild with no wrapper/normalizer/rewrite (`run-20260824-004751`, 38 events) | `everrun-dogfood.md` §Direct Raw Acceptance — Post-Fix; `everrun-history-baseline.md` §8065 post-fix + re-confirmation (`run-20260824-011708`) | **Verified** |
| 8066 — Semantic projection | Source-proven terminal/decision/validation/scope facts project from canonical `event_type`/`payload` only; free-text `payload.outcome` ignored | `everrun-dogfood.md` §8066; `test_projection_lifecycle.py`, `test_projection_decisions.py`, `test_projection_runtime_facts.py` | **Verified** |
| 8067 — Real regression proof | Real pair (`004751`→`011708`) transition matrix matches documented semantics | `everrun-dogfood.md` §8067; `test_regression.py::test_governance_delta_real_everrun_pair_transition_matrix` | **Verified** (comparator; one projection-side ordering gap, §3) |
| 8068 — Source-neutrality lock | Comparator reads no producer identity; behavior locked by tests | `test_regression.py` source/run-id identity tests; pack record now `.done.json` on disk (rename uncommitted) | **Verified** (behavior); record state is a process gap, not a defect |
| 8069 — Semantic-surface freeze | Frozen inventory of implemented canonical semantics | `governance-semantic-surface-freeze.md` (12 dims, 5 transitions, freeze rules) | **Verified** |
| 8070 — Production-derived fixture | `fixtures/runtime-evidence/everrun-postfix-minimal/` distills accepted raw evidence, privacy-screened, no fact added | `test_projection_runtime_facts.py::test_everrun_postfix_minimal_fixture_replays_8066_facts`; fixture on disk | **Verified** |
| 8071 — Direct package regression | Focused end-to-end regression over the fixture through the shared public path | `tests/test_evidence_package_ingest.py`, `tests/test_evidence_package_import.py` | **Verified** |
| 8072 — Real regression golden case | `tests/golden/regression/real_everrun_pair.json` freezes the 8067 pair + full 12-dimension matrix; deterministic | `test_golden_regression.py` (pair + determinism) | **Verified** |
| 8073 — Source-neutral parity | EverRun-derived and second-producer fixtures traverse identical shared pipeline + regression read-model; source label inert | `test_second_producer_conformance.py`; `test_regression.py` (`source_label_inert`, `self_delta_under_relabel_is_identity`) | **Verified** |
| 8074 — Regression-policy audit | Existing ordering re-audited against accepted real cases; no accepted case demonstrated a wrong transition | `governance-semantic-surface-freeze.md` §1.3; `src/ailuros/regression/` unchanged | **Verified** (verification only) |
| 8075 — Release-readiness checkpoint | Readiness gates pass for the 8065–8074 surface; residual gaps enumerated | `governance-release-readiness-2026-08.md` | **Verified** |
| 8076 — Deterministic replay | Fixture replayed twice independently → identical canonical facts, evidence attribution, unknowns stay unknown, warnings not suppressed | `tests/test_production_evidence_replay.py` (disposable SQLite; byte-identical fixture) | **Verified** |
| 8077 — Import/rebuild idempotency | Repeated import `ALREADY_PRESENT` with exact event ids (no collapse/duplication); repeated rebuild stable; conflict on changed content never absorbed | `tests/test_evidence_package_import.py` (import idempotency, rebuild idempotency, conflict tests) | **Verified** |
| 8078 — Unknown-event preservation | Unknown/private events preserved losslessly with traceable identity; never projected into invented governance semantics; warning-not-error | `test_second_producer_conformance.py` (`test_unknown_producer_specific_event_is_preserved_not_dropped`, `test_unknown_events_survive_without_promoting_clean_across_canonical_fixtures`, `test_second_producer_unsupported_event_type_is_warning_not_error`) | **Verified** |
| 8079 — Scope-conflict controls | Scope-aware `evidence_inconsistency` boundary locked both directions: cross-scope no signal (negative), same-scope+domain signal (positive), provenance to source refs | `tests/test_governance_signals.py` (`test_negative_control_real_incident_accept_continue_across_scopes`, `test_negative_control_conflict_vocabulary_across_distinct_scopes`, `test_positive_control_same_scope_and_domain_conflict_remains`, `test_evidence_inconsistency_signal_points_to_source_evidence_refs`) | **Verified** |
| 8080 — Producer compatibility matrix | Exactly two proven producers (EverRun fixture, second-producer fixture) through one parameterized shared pipeline; unproven frameworks explicitly excluded | `tests/test_producer_compatibility_matrix.py` (`test_matrix_inventory_is_exactly_the_evidence_backed_producers`, `test_shared_pipeline_is_parameterized_not_branched`, `test_proven_boundary_excludes_unproven_frameworks`) | **Verified** |
| 8081 — Governance regression corpus | `fixtures/governance-regression/cases/*.json` (two cases) pre-declare facts/transitions/refs; comparator reproduces them; fixture sides project via production path; coverage gaps reported not synthesized | `tests/test_regression_corpus.py`; `cases/real_everrun_pair_8067.json`, `cases/everrun_second_producer_parity.json` | **Verified** |

**T1 conclusion:** all predecessor evidence required by this pack is present and
verifiable. No required predecessor is blocked by a correctness defect.

---

## 2. T2 — Capability classification per canonical surface area

Status vocabulary: **implemented** = code + locking tests exist; **proven** =
supported by accepted real or production-derived evidence; **partially-proven** =
proven on some inputs but not others (evidence-missing on real inputs);
**unproven** = mechanism only synthetic/fixture, no production evidence.

| Canonical surface area | Status | Evidence |
|---|---|---|
| Direct raw EverRun acceptance (audit → import → rebuild) | **Proven** | 8065 post-fix, `run-20260824-004751`, re-confirmed `run-20260824-011708`; `everrun-dogfood.md` §8065 |
| Semantic projection (terminal/decision/validation/scope from `event_type`/`payload` only) | **Proven** | 8066; `test_projection_lifecycle.py`, `test_projection_decisions.py`, `test_projection_runtime_facts.py` |
| Lifecycle | **Partially-proven** | Proven derivation; real exports freeze at `running` (no `run_completed`), so `completed`/`failed` terminal states are test-proven only |
| Outcomes (native `Outcome`) | **Partially-proven** | Real pair yields `unknown`; `success`/`partial`/`blocked`/`review_required`/`failed` precedence test-proven only |
| Outcomes (governed `GovernedOutcome`) | **Partially-proven** | Real pair yields `unknown` (never promoted to clean); precedence `FAILED > REVIEW_REQUIRED > UNKNOWN > DEGRADED > CLEAN` synthetic-proven (`test_governed_outcome.py`) |
| Authority / Approval / Budget | **Partially-proven** | State derivation implemented + test-proven; real EverRun exports carry no such records → coverage `unknown` (evidence-missing), never promoted |
| Scope (clean/violated/unknown + scope_ref propagation) | **Proven** | `project_scope` `status=clean` projects in real export; scope_ref propagation `test_projection_decisions.py`, `test_second_producer_conformance.py` |
| Validation | **Proven** | `project_validation` `status=passed` projects in real export |
| Signals (incl. scope-aware `evidence_inconsistency`) | **Proven** | Real `accept`/`continue` mix → no false positive (negative control); same-scope conflict retained (positive control); 8079 controls |
| Coverage (evaluated/unknown/not_applicable) | **Proven** (evaluated) / **Partially-proven** (unknown on real) | validation/scope `evaluated` on real pair; authority/approval/budget `unknown` evidence-missing |
| Provenance / evidence attribution | **Proven** | `evidence_refs` retained and resolve to stored events (8076 replay asserts identical refs both replays); 8061 |
| Temporal attribution (timezone-aware invariants) | **Proven** | `test_temporal_governance.py`; real exports carry tz-aware timestamps |
| Regression delta (12 dims, 5 transitions, source-neutral) | **Proven** | 8072 golden case, 8073 parity, 8074 audit, 8081 corpus; `compare_governance_projections` |
| Unknown-event preservation (lossless, no clean promotion) | **Proven** | 8078; 34 real unknown event types preserved as `source_preserved_unknown`; `test_second_producer_conformance.py` |
| Deterministic replay | **Proven** | 8076 `test_production_evidence_replay.py` |
| Import/rebuild idempotency + conflict detection | **Proven** | 8077 `test_evidence_package_import.py` |
| Producer compatibility matrix (proven producers) | **Proven** | 8080 `test_producer_compatibility_matrix.py` (exactly two, parameterized pipeline) |
| Regression corpus (bounded, pre-declared) | **Proven** | 8081 `test_regression_corpus.py` |
| Real external integrations beyond EverRun (LangGraph, OpenAI Agents SDK, MCP server, …) | **Unproven** | Explicitly excluded by the 8080 matrix boundary (`test_proven_boundary_excludes_unproven_frameworks`); no such integration is claimed |

**T2 conclusion:** every surface area listed in the 8069 freeze inventory remains
implemented and locked. Surfaces that real exports leave evidence-missing
(lifecycle terminal states, native/governed outcome values other than
`unknown`, authority/approval/budget facts) are classified **partially-proven**,
never promoted to supported. No unknown/unproven item is converted into
supported. No roadmap capability is added to fill a gap.

---

## 3. T3 — Open gaps

Separated into correctness defects (open, non-blocking, fixable under the
freeze's correctness/conformance allowance) and evidence-coverage gaps (recorded
for new production evidence; not fixed here).

### 3.1 Correctness defects (open, non-blocking)

1. **Terminal-event ordering gap.** The real export writes terminal
   `run_completed` before `run_started`, so `build_execution_projection` derives
   `lifecycle=running` despite the `success` fact. Fix belongs to
   `src/ailuros/projection.py`; out of scope here (source projections are not
   mutated). Evidence: `everrun-dogfood.md` §8067.
2. **8068 record-state gap (process, not behavior).** The 8068 pack record is
   `sdd/task-dir/8068.*.todo.json` in git but `.done.json` on disk (rename
   uncommitted at check time). The source-neutrality behavior itself is
   mechanically locked by `test_regression.py`; this is a bookkeeping gap only,
   and it is **not** a blocking correctness defect.

### 3.2 Evidence-coverage gaps (recorded, not fixed, not promoted)

1. **No `run_completed` event in real exports (evidence-missing).** The accepted
   real pair freezes at `lifecycle=running`, `outcome=unknown`,
   `governed_outcome=unknown` (`completed_at=null`). 8067-era P2.
2. **34 unknown event types in real exports (mapping-missing).**
   `backend.*`, `projection.*`, `session.fallback`, … preserved as
   `source_preserved_unknown`; never inferred clean.
3. **Authority/approval/budget coverage in real exports (evidence-missing).**
   No such records; coverage stays `unknown`/not evaluated.
4. **`planner_proposed_accept_and_no_blocking_rule_triggered` (open question).**
   `execution_control` vocabulary (`accept`/`continue`/`human_review`) is not
   `block`/`require_review`, so native outcome stays `unknown` for the accepted
   running-lifecycle pair. Projection-vocabulary open question, not a
   regression-transition defect. Evidence: `governance-semantic-surface-freeze.md`
   §1.3.
5. **Ranked transitions (`improved`/`regressed`/`incomparable`) unproven on real
   data.** Only synthetic tests exercise them; the 8081 corpus explicitly
   reports this coverage gap and requires a new real case to update it.
6. **Multi-run longitudinal regression not built.** Read model compares two built
   projections post-run only.
7. **8068 contract claim (insufficient-evidence, record-keeping).** The pack
   declared `production_path: true` but delivered a behavioral test-lock; the
   behavior is locked and the record is `.done` on disk.
8. **Duplicated regression module (housekeeping note).** Package
   `src/ailuros/regression/` and standalone `src/ailuros/regression.py` carry
   identical semantics; behavior identical and locked.

No fix is invented for any gap above. Correctness defect #1 remains explicitly
open and non-blocking; evidence-coverage gaps #1–#6 are the target inputs for
future production evidence.

---

## 4. T4 — Full validation re-run

Command (run unchanged, no test modifications, on 2026-08-24):

```
python -m pytest tests -q
```

Result: **1482 passed** in ~130s, 1 warning. The single warning is the
environmental `PytestCacheWarning` (`could not create cache path … [WinError 183]`
— Windows pytest cache-path creation; unrelated to the suite, identical class to
the warning recorded in the 8069 freeze doc and the 8075 readiness doc). No
failures, no skipped, no test modifications. The count is 46 higher than the
8075-era clean baseline (1436), matching the replay/idempotency/unknown/
conflict-control/matrix/corpus tests added by 8076–8081.

---

## 5. T5 — Freeze next-step rule

Effective from this baseline:

- **Post-8082 semantic expansion requires new production evidence.** Any new
  top-level governance primitive, new regression dimension (beyond the 12), new
  transition (beyond the 5), new runtime/control path, or extension of a
  partially-proven surface into a supported claim requires (a) new production
  evidence — a real package or dogfood finding demonstrating the missing
  capability — and (b) a governance pack carrying that evidence. A pack title or
  a roadmap entry alone is not evidence. This is the same gate as
  `governance-semantic-surface-freeze.md` §3.3.
- **Correctness/conformance fixes remain allowed.** Fixing the terminal-event
  ordering defect (§3.1), improving evidence attribution/conflict correctness,
  and tightening consumer-side producer conformance remain in scope during the
  freeze (mirrors `governance-semantic-surface-freeze.md` §3.1).
- **Unknowns are never promoted.** Every evidence-missing or mapping-missing
  surface stays classified as such until real evidence arrives; expected-unknown
  is not a failure and is not converted into a supported claim.

---

## 6. Red-line compliance

- **No blocking predecessor.** All required predecessor evidence (8065–8081) is
  verified; the only non-`.done` record (8068) is a process/bookkeeping gap with
  mechanically locked behavior, not a blocking correctness defect. The baseline
  is therefore ready to freeze.
- **Unknown/unproven not converted to supported.** T2 explicitly classifies
  partially-proven and unproven surfaces; nothing is promoted.
- **No roadmap capability added to fill gaps.** §3 records gaps without
  inventing fixes or features.
