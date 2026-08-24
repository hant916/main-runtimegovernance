# Governance Release Readiness — 2026-08

**Status:** Freeze checkpoint (pack 8075). Records whether the Ailuros governance
evaluator/regression surface is ready to freeze as the next trusted baseline,
and enumerates only evidence-backed residual gaps.
**Scope:** The 8065–8074 convergence line closed by the semantic-surface freeze
(`governance-semantic-surface-freeze.md`). Documentation only; no production or
test change.
**Evidence basis:** Pack records and .done checkpoints in `sdd/task-dir`,
`docs/operations/everrun-dogfood.md`, `docs/dogfood/everrun-history-baseline.md`,
`docs/architecture/governance-semantic-surface-freeze.md`, the committed golden
case and fixtures, and the full clean validation suite.

---

## 1. Predecessor evidence (T1) — implemented vs production-proven

Source of truth is current code + tests, not pack titles. Each capability below
is classified as **production-proven** (direct raw producer acceptance or a
source-derived real pair), **test/synthetic-only** (mechanism proven by
synthetic or fixture evidence only), or **unresolved** (open gap).

| Pack | Capability | Classification | Evidence |
|---|---|---|---|
| 8065 — Direct raw acceptance | Raw EverRun `evidence/` output is directly consumable: audit ok=true/warn, import `created` (38 events), rebuild completes (`lifecycle=running`, `validation=passed`, `scope=clean`, `execution_control/human_review`) with no wrapper/normalizer/rewrite | **Production-proven** | `everrun-dogfood.md` §Direct Raw Acceptance — Post-Fix; `run-20260824-004751`; re-confirmed on `run-20260824-011708` |
| 8066 — Semantic projection | Source-proven terminal/decision/validation/scope facts project into canonical fields from `event_type`/`payload` only; free-text `payload.outcome` deliberately ignored | **Production-proven** (verification only) | `test_projection_lifecycle.py`, `test_projection_decisions.py`, `test_projection_runtime_facts.py` |
| 8067 — Real regression proof | Comparator transition matrix on real pair (`004751`→`011708`) matches documented semantics; no comparator defect | **Production-proven** (comparator); one projection-side ordering gap open | `test_regression.py::test_governance_delta_real_everrun_pair_transition_matrix` |
| 8068 — Source-neutrality lock | Comparator reads no producer identity; behavior locked by tests; pack `production_path: true` contract claim was a test-lock deliverable | **Production-proven** behavior; **insufficient-evidence** for the `production_path` claim as written | `test_regression.py` source/run-id identity tests; pack record now `.done.json` |
| 8070 — Production-derived fixture | `fixtures/runtime-evidence/everrun-postfix-minimal/` distills the accepted raw evidence, privacy-screened, no governance fact added | **Production-proven** (derived from accepted package) | `test_projection_runtime_facts.py::test_everrun_postfix_minimal_fixture_replays_8066_facts` |
| 8071 — Direct package regression | Focused end-to-end regression test over the fixture through the shared public path | **Production-proven** (fixture-derived) | `tests/test_evidence_package_ingest.py` |
| 8072 — Real regression golden case | `tests/golden/regression/real_everrun_pair.json` freezes the 8067 pair and full 12-dimension transition matrix; deterministic | **Production-proven** | `test_golden_regression.py` (pair + determinism) |
| 8073 — Source-neutral parity | EverRun-derived and second-producer canonical fixtures traverse the identical shared pipeline and regression read-model; source label inert | **Production-proven** (canonical fixtures) | `test_second_producer_conformance.py` (`identical_shared_pipeline`, `source_label_is_inert`, `unknown_events_survive`); `test_regression.py` (`source_label_inert`, `self_delta_under_relabel_is_identity`) |
| 8074 — Regression-policy audit | Existing ordering re-audited against accepted real cases; no accepted case demonstrated a wrong transition; no ranking changed | **Production-proven** (verification only) | `governance-semantic-surface-freeze.md` §1.3; `src/ailuros/regression/` unchanged |

### 1.1 Synthetic-only (mechanism, not production-ordering) evidence

- Comparator `improved`/`regressed`/`incomparable` transitions are exercised
  only by synthetic tests (`test_regression.py`
  `test_governance_delta_detects_regressions_across_available_facts`,
  `test_governance_delta_detects_improvement_and_ignores_producer_identity`).
  No accepted real case exercises a non-`unknown`/non-`unchanged` transition, so
  the relative ordering of non-`unknown` states is not proven wrong — but also
  not production-proven right.
- Cross-scope discrimination (`accept` vs `continue` producing no
  `evidence_inconsistency` signal) was proven on a faithful conformant copy of
  `run-20260823-033016` (`everrun-history-baseline.md` §8064), a documented
  replay artifact, not a direct raw export.
- `review_required`/`blocked` precedence and aggregate governed-outcome
  precedence are locked by synthetic aggregation tests only
  (`test_governed_outcome.py`).

---

## 2. Readiness gates (T2)

| Gate | Required evidence | Result | Evidence |
|---|---|---|---|
| Direct raw EverRun audit/import/rebuild success | Raw `evidence/` output enters audit → import → rebuild with no wrapper/normalizer/rewrite | **PASS** | 8065 post-fix, `run-20260824-004751` (audit ok=true/warn errors=[]; import created 38/0; report completes), re-confirmed `run-20260824-011708`; `everrun-dogfood.md` §8065 |
| Source-proven lifecycle/decision/validation/scope projection | Terminal/decision/validation/scope facts project from canonical `event_type`/`payload`; no free-text invention; missing evidence stays conservative | **PASS** | 8066; `test_projection_lifecycle.py`, `test_projection_decisions.py`, `test_projection_runtime_facts.py` |
| Real regression golden case + source-neutral second-producer parity | At least one real frozen pair; second-producer traverses the identical pipeline with inert identity | **PASS** | 8072 golden (`real_everrun_pair.json`, `test_golden_regression.py`); 8073 parity (`test_second_producer_conformance.py`) |
| Regression-policy audit, no unresolved proven contradiction | No accepted real case yields a factually wrong governance delta | **PASS** | 8074 re-audit; no accepted case demonstrated a wrong transition (§1.3 of the freeze doc) |

All four gates pass. The remaining items in §3 are open questions, expected
unknowns, or documentation-precision notes — none is a proven contradiction of
the frozen regression policy, so the baseline may be frozen with them explicit.

---

## 3. Frozen baseline (T3)

The following are the frozen post-dogfood trusted baseline, effective as of
2026-08-24. They are the responsibility of the frozen records below and must
not be modified without a new governance pack carrying production evidence.

- The 12 governance dimensions, their rank tables, the 5 transitions, and
  `compare_governance_projections` source-neutrality contract
  (`src/ailuros/regression/` package; frozen by
  `governance-semantic-surface-freeze.md` §5 and the 8072 golden case).
- The evidence-package contract (`ailuros.timeline.v1`): manifest with
  `files[].name`, timeline object with `events` array.
- Direct raw producer acceptance of the post-fix EverRun export shape
  (`run-20260824-004751`), with all unknowns classified as expected-unknown and
  never promoted to clean.
- The projection rule that free-text `payload.outcome` is ignored for
  terminal-state derivation; source-proven semantics are driven by canonical
  `event_type`/`payload` fields only.
- The residual-gap inventory in §4 below is part of the baseline: any change to
  the 12/5 regression surface, a new top-level primitive, or a new runtime
  path still requires the roadmap gate in `governance-semantic-surface-freeze.md`
  §3.3.

---

## 4. Residual gaps (evidence-backed, ranked)

Ranked by production evidence; no future feature is invented.

1. **Terminal-event ordering gap (production-proven evidence).** The real
   export writes the terminal `run_completed` event before `run_started`, so
   `build_execution_projection` derives `lifecycle=running` despite the terminal
   `success` fact being present. Fix belongs to `src/ailuros/projection.py`;
   out of scope here (source projections are not mutated). Evidence:
   `everrun-dogfood.md` §8067. **Open, non-blocking** for this baseline but
   material to the "terminal state proof" claim — the frozen real pair is a
   running-lifecycle pair, not a completed one.
2. **Exporter emits no `run_completed` event (evidence-missing).** Real
   exports carry no terminal lifecycle event, so the accepted pair freezes at
   `lifecycle=running`, `outcome=unknown`/`governed_outcome=unknown`. This is
   the 8067-era P2 gap. Evidence: `everrun-history-baseline.md` §8064 remaining
   gaps; report `completed_at=null`.
3. **34 unknown event types in real exports (mapping-missing).**
   `backend.*`, `projection.*`, `session.fallback`, … are registry gaps,
   preserved as `source_preserved_unknown`, never inferred clean. Evidence:
   `everrun-dogfood.md` §8065 post-fix audit warnings
   (`coverage.source_preserved_unknown=31`).
4. **Authority/approval/budget coverage in real exports (evidence-missing).**
   The real packages carry no such records; coverage stays `unknown`/not
   evaluated. Evidence: `everrun-dogfood.md` §8065 T4.
5. **`planner_proposed_accept_and_no_blocking_rule_triggered` (open question).**
   `execution_control` vocabulary (`accept`/`continue`/`human_review`) is not
   `block`/`require_review`, so native outcome stays `unknown` for the accepted
   running-lifecycle pair. Projection-vocabulary open question, not a
   regression-transition defect. Evidence: `governance-semantic-surface-freeze.md`
   §1.3.
6. **Multi-run longitudinal regression (not built).** The read model compares
   two built projections post-run; no cross-run delta mechanism exists.
   Evidence: `everrun-dogfood.md` §Optional Repeated-Run Governance Delta.
7. **Documentation/module-precision note: duplicated regression module.**
   The imported regression code is the package
   `src/ailuros/regression/` (`__init__.py` → `governance_delta.py`); a
   standalone duplicate `src/ailuros/regression.py` also exists with identical
   semantics, and the 8074 audit (§1.3 of the freeze doc) cites its line
   numbers. Behavior is identical and locked; the duplication and the doc
   pointer are a housekeeping note, not a behavior gap.
8. **8068 pack contract claim (insufficient-evidence).** The pack declared
   `production_path: true` but delivered a behavioral test-lock. The behavior
   is mechanically locked and the pack record is now `.done.json`, so this is a
   residual record-keeping note, not a defect.

No gap above is a failed direct-producer or regression gate hidden as an
expected unknown: every accepted real input is documented, and each unknown is
explicitly classified as evidence-missing, mapping-missing, or a non-blocking
open question with its evidence.

---

## 5. Final validation (T4)

Run unchanged on 2026-08-24:

```
python -m pytest tests -q
```

Result: **1436 passed** in ~85s, 1 environmental warning (pytest cache path
creation on Windows: WinError 183 — unrelated to the suite). No failures, no
test modifications, no production changes. (This mirrors the clean baseline
recorded in `governance-semantic-surface-freeze.md` §4.)

---

## 6. Freeze claim and boundary

The Ailuros governance evaluator/regression surface is **ready to freeze as the
next trusted baseline** for the evidence boundary proven in §2: direct raw
EverRun acceptance, source-proven projection of the observed shapes,
real regression golden evidence with source-neutral second-producer parity, and
a regression-policy audit with no unresolved proven contradiction. This is a
bounded convergence claim for the 8065–8074 surface, not a claim of universal
governance convergence: §4 residual gaps remain explicit, no new top-level
primitive is asserted, and all disallowed freeze-scope work
(`governance-semantic-surface-freeze.md` §3.2) stays out.
