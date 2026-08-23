# EverRun History Dogfood Baseline

## Purpose and boundary

This is a deterministic, evidence-first baseline over a fixed sample of ten
EverRun controller-history runs. It records only stable run identifiers and
compact native-fact summaries. It deliberately does **not** contain raw
`.everrun/history` content, prompts, patches, logs, or generated reports.

The sampled controller records are not `runtime-evidence-package-v1` packages.
Consequently they cannot be imported into Ailuros without an out-of-scope
history-to-package transformation. The Ailuros result for every row is therefore
`unknown` / not evaluated, never inferred to be clean. This is an
**expected unknown**, not a new blocked or human-review path.

Evidence references below are local-only pointers to the controller result for
the named run and iteration: `.everrun/history/<run-id>/<iteration>/controller-result.json`.
They are sufficient to reproduce the native-fact summary locally, but the
referenced history remains uncommitted.

## Fixed representative sample

| Sample | Coverage | EverRun-native facts | Ailuros-derived result | Human expected governance judgment and evidence | Classification |
|---|---|---|---|---|---|
| `0002.validate-evidence-package-contract` | Clean success | Iteration 001: `final_decision=accept`, validation passed, scope passed/clean. | `unknown` — no canonical package; not evaluated. | Clean success. Evidence: iteration 001 controller result. | Expected unknown |
| `0004.add-markdown-audit-report-demo` | Validation failure, then recovery | Iteration 001 recorded `validation_failed_unknown_scope`; iteration 002 accepted with passed validation and clean scope. | `unknown` — no canonical package; not evaluated. | Eventual success after a validation recovery; the first attempt must not be represented as clean. Evidence: iterations 001–002 controller results. | Expected unknown |
| `run-20260511-192006` | Validation failure / bounded retry | Four attempts began with `tests_failed` and ended `human_review` / `max_iterations_reached`. | `unknown` — no canonical package; not evaluated. | Review required for unresolved validation failure. Evidence: iterations 001–004 controller results. | Expected unknown |
| `0005H.copy-clarify-canonical-sample-handoff` | Retry/reject behavior | Validation-unknown retries exhausted; final decision `human_review`, validation failed. | `unknown` — no canonical package; not evaluated. | Review required; do not convert the failed validation into a clean result. Evidence: iterations 001–002 controller results. | Expected unknown |
| `run-20260521-233756` | Multi-attempt convergence | First attempt `tests_failed`; fourth attempt accepted. | `unknown` — no canonical package; not evaluated. | Eventual success, with earlier failure retained as history. Evidence: iterations 001 and 004 controller results. | Expected unknown |
| `run-20260525-121225` | Changed-file anomaly | Controller recorded `git_evidence_inconsistent` and final `human_review`. | `unknown` — no canonical package; not evaluated. | Review required for changed-file evidence mismatch. Evidence: iteration 001 controller result. | Expected unknown |
| `run-20260604-172320` | Scope anomaly | Validation passed, but controller recorded `forbidden_file_touched` and final `human_review`. | `unknown` — no canonical package; not evaluated. | Review required for the recorded forbidden-path anomaly; passing validation alone is insufficient. Evidence: iteration 001 controller result. | Expected unknown |
| `run-20260510-224338` | Known historical incident | Controller recorded `codex_session_failed` and final `human_review`. | `unknown` — no canonical package; not evaluated. | Insufficient governance evidence; record the execution incident without calling it a policy violation. Evidence: iteration 001 controller result. | Expected unknown |
| `0001.load-canonical-evidence-package` | Reject / partial outcome | A zero-diff permission gate was recorded first; later result was `partial_with_report` with semantic failure and failed validation. | `unknown` — no canonical package; not evaluated. | Review required for unresolved semantic/validation failure. Evidence: iterations 001–002 controller results. | Expected unknown |
| `0001.validate-clarify-evidence-bundle` | Known environment incident | Final state was `partial_with_report`; validation was not executable and implementation preflight failed. | `unknown` — no canonical package; not evaluated. | Insufficient evidence for a governance judgment; retain as an environment incident. Evidence: iterations 001–004 controller results. | Expected unknown |

## Baseline result

| Measure | Count |
|---|---:|
| Sampled runs | 10 |
| Expected unknown | 10 |
| True positive | 0 |
| False negative | 0 |
| False positive | 0 |
| Pipeline failure | 0 |

This is an input-coverage baseline, not a rule-quality score: without a
canonical evidence package, no Ailuros governance decision exists to compare
with the human expectation. The zero counts for true/false positives and
negatives must not be read as validation of the production rules.

## 8051 convergence re-run and acceptance record

This re-run preserves the fixed ten-run selection and the human expectations
above. It was assessed after 8048 (external-evidence projection normalization)
and 8050 (governance regression delta) without changing historical inputs.

The production package path has a strict input gate: each selected controller
record remains controller history, not a canonical package with `manifest.json`
and `timeline.json`. Consequently no selected record can enter
load/ingest/rebuild/report without an out-of-scope history transformation. The
post-fix result is therefore still `unknown` / not evaluated for every row. This
is the documented expected-unknown result, not a pipeline failure, BLOCKED
state, HUMAN_REVIEW state, or promotion to clean.

| Sample | Before | Post-8048/8050 classification | Convergence status | Evidence-backed reason |
|---|---|---|---|---|
| `0002.validate-evidence-package-contract` | Expected unknown | Expected unknown | Expected unknown | No canonical package exists for the selected controller record. |
| `0004.add-markdown-audit-report-demo` | Expected unknown | Expected unknown | Expected unknown | No canonical package exists for the selected controller record. |
| `run-20260511-192006` | Expected unknown | Expected unknown | Expected unknown | No canonical package exists for the selected controller record. |
| `0005H.copy-clarify-canonical-sample-handoff` | Expected unknown | Expected unknown | Expected unknown | No canonical package exists for the selected controller record. |
| `run-20260521-233756` | Expected unknown | Expected unknown | Expected unknown | No canonical package exists for the selected controller record. |
| `run-20260525-121225` | Expected unknown | Expected unknown | Expected unknown | No canonical package exists for the selected controller record. |
| `run-20260604-172320` | Expected unknown | Expected unknown | Expected unknown | No canonical package exists for the selected controller record. |
| `run-20260510-224338` | Expected unknown | Expected unknown | Expected unknown | No canonical package exists for the selected controller record. |
| `0001.load-canonical-evidence-package` | Expected unknown | Expected unknown | Expected unknown | No canonical package exists for the selected controller record. |
| `0001.validate-clarify-evidence-bundle` | Expected unknown | Expected unknown | Expected unknown | No canonical package exists for the selected controller record. |

There were no prior false negatives, false positives, or pipeline failures in
the 8047 baseline, so none can change classification in this comparison. The
8050 governance delta is not applicable: it compares two built
`ExecutionProjection` objects, and no projection may be built from these
non-package inputs. 8048 fixes projection of valid wrapped package events; it
does not supply or infer the missing package for a controller-history record.

| Finding status | Count | Record |
|---|---:|---|
| Fixed | 0 | No historical classification changed. |
| Still open | 0 | No previously evaluated governance finding exists in this sample. |
| Expected unknown | 10 | All selected inputs remain non-importable controller history. |
| Newly discovered | 0 | The re-run introduced no new gap. |

### Acceptance and next batch

The 8051 dogfood batch is **accepted for this bounded historical baseline**:
the post-fix behavior preserves all ten expected-unknown judgments, makes no
unknown-to-clean promotion, and introduces no non-capability BLOCKED or
HUMAN_REVIEW path. It is not an end-to-end acceptance of package
load/ingest/rebuild/report for these runs, because the required canonical
handoff is absent.

The sole candidate for a future pack remains the existing P0 gap: a lossless,
privacy-screened export of selected controller history to
`runtime-evidence-package-v1`, followed by a separately scoped real package
rerun. No implementation is made by this record.

## Evidence limitations

- The historical controller records provide terminal decisions, validation and
  scope facts when present, but are not the Ailuros evidence-package handoff.
- No history was transformed or backfilled to make absent fields look clean.
- 8048 normalizes valid wrapped package event types at the projection boundary;
  this historical baseline cannot exercise that fix because it contains no
  canonical packages.
- An expected judgment is based only on the cited native controller result. If a
  future sample lacks that result, its expected judgment must be marked
  **insufficient evidence** rather than inferred.

## Ranked, evidence-backed gap candidates

1. **P0 — Establish a lossless, privacy-screened export from selected EverRun
   history runs to `runtime-evidence-package-v1`.** Evidence: every sampled
   record is non-importable as-is, leaving all ten Ailuros outcomes unknown.
   Acceptance must preserve native event identity and mark unavailable fields
   unknown; it must not synthesize a clean result.
2. **P1 — Project original event types from imported evidence-package wrappers.**
   Evidence: the existing second-producer conformance limitation documents that
   imported packages preserve raw evidence but can project as unknown. This is a
   pre-existing derived-projection gap, not a source-specific defect.
3. **P2 — Add a repeatable operator selection manifest outside runtime history.**
   Evidence: this fixed ID list is reproducible, but each future baseline needs
   the same separation of native facts, derived result, expected judgment, and
   evidence reference.

No implementation change is proposed by this baseline. Gap candidates require
their own scoped work before runtime or governance behavior changes.

## 8064 boundary convergence re-run and final record

This is the final convergence record for the external governed-execution
boundary after packs 8052-8063. It re-runs the bounded real EverRun dogfood
evidence and classifies every prior finding. The record is documentation-only;
it changes no production, test, or governance code.

### Sample availability and equivalent evidence rationale

The original run identifier referenced by this batch is `run-20260822-180944`.
It is **not present** in the local `.everrun/history` directory (only
`run-20260823-*` runs exist), so the exact original export cannot be replayed
verbatim. This is the documented unavailability exception allowed by the pack.

The **equivalent real evidence** used is the canonical EverRun export
`run-20260823-033016` (`.everrun/history/run-20260823-033016/evidence/`), which
is the run that actually executed packs 8055-8063. Its manifest carries the
identical conflict class this boundary batch targets:

- `EVIDENCE_CONFLICT`: "Conflicting governance decisions in same execution
  scope (unknown scope (no pack/iteration metadata)): ['accept', 'continue']"
  with 10 source refs (9 `accept` + 1 `continue` governance decisions).

The export is not `runtime-evidence-package-v1` conformant as shipped (flat
timeline, `schema_version: "1.0"`, no `files` array). For the re-run it was
copied into a faithful conformant `ailuros.timeline.v1` package with **all 196
events unchanged** (same event ids, types, timestamps, payloads; no new facts,
no dropped facts). This transformation is documented here and is the same
lossless-export gap already ranked as P0 below.

### T1: Production path re-run

The faithful conformant copy of `run-20260823-033016` was executed through the
production Ailuros load/ingest/projection/signals/governed-result path:

| Step | Result |
|---|---|
| Contract validation | `ok`, 0 errors, 183 warnings (unknown event types preserved) |
| `evidence-audit` | `ok`, decision `warn` |
| `load_evidence_package` | loaded, `run-20260823-033016`, `everrun`, 196 events |
| `ingest_evidence_package` | `created`, 196 imported, 0 skipped, 0 conflicts |
| Rebuild projection/signals | 10 decisions, 53 evidence refs, 0 signals |
| Governed result | `unknown` (no clean promotion) |

Native facts derived: lifecycle `running` (no `run_completed` in the export),
native outcome `unknown`, governed outcome `unknown`, validation `unknown`,
scope `unknown`, all coverage dimensions `unknown`, `scope_ref` none. Ten
governance decisions project as `source_preserved_unknown` with no `scope_ref`
because the exporter emits no pack/iteration scope metadata.

**Key result:** the `accept` / `continue` mix does **not** produce an
`evidence_inconsistency` signal. The known run-wide false-positive class is
closed: sibling scopes (here packs) with different decisions are no longer
flagged as conflicts solely due to run-wide aggregation.

### T2: Scope semantics verification

- **Cross-scope differences do not create a conflict.** The real sample's
  `accept` + `continue` decisions do not trigger `evidence_inconsistency`.
  `_evidence_inconsistency_rule` groups by `(scope_ref, projected_domain)`,
  so sibling scopes with different decisions are never conflated. Proven by
  `tests/test_governance_signals.py`:
  `test_no_evidence_inconsistency_across_different_scopes`,
  `test_no_evidence_inconsistency_unscoped_vs_scoped`,
  `test_evidence_inconsistency_conflict_is_isolated_per_scope`.
- **Same-scope contradictions remain detectable.** An `allow` + `block` (or
  `allow` + deny-pattern) pair within the **same** `scope_ref` still produces
  an `evidence_inconsistency` signal. Proven by
  `test_evidence_inconsistency_same_scope_and_domain_conflicts` and
  `test_evidence_inconsistency_allow_and_block_same_domain`.

### T3: Governed result and provenance

- Lifecycle `running`, native outcome `unknown`, governed outcome `unknown` —
  recorded separately, never merged, never promoted to clean.
- Coverage all `unknown` (no authority/approval/budget/validation/scope
  evidence in the export), consistent with the second-producer conformance
  rule that missing constraints are never inferred as clean.
- Scoped signals: none derived; no `scope_ref` present in the export.
- Temporal attribution: all timestamps are timezone-aware; `run_started`
  events are preserved; no `run_completed` event exists, hence lifecycle
  `running` and governed outcome `unknown`.
- Evidence refs: 53 projection refs retained and traceable to stored events
  (each decision and each lifecycle/validation/scope event keeps its
  `event_id`). `build_governed_execution_result` and `build_run_report` both
  carry them.
- Review-required visibility at aggregate level: no review-required scope is
  present in this sample, so the aggregate is `unknown`. The invariant is
  proven by `tests/test_governed_outcome.py`:
  `test_aggregate_review_required_dominates_clean_scopes` and
  `test_aggregate_review_required_dominates_degraded_scopes` — a
  `review_required` scope prevents a clean or degraded success claim.

### T4: Convergence classification

| Finding | Before | After 8052-8063 | Responsible pack | Evidence |
|---|---|---|---|---|
| Cross-scope decisions flagged as conflicts (run-wide aggregation) | False positive | **Fixed** — no `evidence_inconsistency` for `accept`+`continue` | 8056 scope-governance-decision-consistency, 8058 aggregate-multi-scope-governed-outcome | Real export re-run; `test_no_evidence_inconsistency_across_different_scopes` |
| Execution scope not carried through the pipeline | Open | **Fixed** — `scope_ref` propagates load→ingest→projection→signals | 8053 add-execution-scope-reference, 8054 propagate-scope-through-evidence-pipeline | `tests/test_projection_decisions.py` external-wrapper tests; `test_second_producer_scoped_evidence_scope_survives_canonical_pipeline` |
| Authority/approval/budget records not bound to scope | Open | **Fixed** | 8055 scope-governance-records | `tests/test_authority_governance.py`, `test_approval_governance.py`, `test_budget_governance.py` |
| Signals not scope-aware | Open | **Fixed** | 8057 make-governance-signals-scope-aware | `tests/test_governance_signals.py` T1 signal-identity tests |
| No multi-scope governed outcome aggregation | Open | **Fixed** — precedence `FAILED > REVIEW_REQUIRED > UNKNOWN > DEGRADED > CLEAN`; UNKNOWN never inferred clean | 8058 aggregate-multi-scope-governed-outcome | `tests/test_governed_outcome.py` aggregation tests |
| No stable governed-execution result contract | Open | **Fixed** | 8059 add-governed-execution-result-contract | `tests/test_governed_execution_result.py` |
| Temporal attribution invariants missing | Open | **Fixed** | 8060 add-temporal-governance-invariants | `tests/test_temporal_governance.py` |
| Signal evidence provenance too broad | Open | **Fixed** — record-backed causes narrowed | 8061 tighten-signal-evidence-provenance | `tests/test_governance_signals.py` evidence-provenance tests |
| Producer conformance not hardened for scope/provenance | Open | **Fixed** | 8062 harden-producer-conformance-scope-provenance | `tests/test_second_producer_conformance.py`, `test_adapter_conformance.py` |
| Canonical governance surface not audited/frozen | Open | **Fixed** | 8063 audit-canonical-governance-surface | `docs/architecture/canonical-governance-surface.md`, `tests/test_core_boundary.py` |

Status summary for this re-run: **Fixed 9**, **Still open 0**, **Expected
unknown 1** (the real sample's governed result is `unknown` because the export
lacks run-completion and scope metadata — this is expected-unknown, not a
failure), **Newly discovered 0**.

### Acceptance and remaining gaps

The 8064 batch is **accepted for this bounded convergence**: the real sample
is re-evaluated through the production path after 8052-8063, the known
cross-scope false-positive class is closed without suppressing true
same-scope conflict semantics, unknown evidence stays preserved and
unpromoted to clean, and no production or test file was modified.

Remaining gaps are seeded as candidate future packs (not implemented here):

1. **P0 — Lossless, privacy-screened EverRun export to
   `runtime-evidence-package-v1`.** Evidence: the real export is
   non-conformant as shipped and carries no pack/iteration scope metadata or
   `run_completed` event; the re-run required a documented faithful
   transformation and still produced an `unknown` governed result.
2. **P1 — Scope attribution from EverRun pack/iteration metadata.** Evidence:
   all 10 real governance decisions project to `scope_ref=None` because the
   exporter does not emit pack/iteration scope; sibling-scope discrimination
   is therefore only test-proven, not sample-proven.
3. **P2 — Emit `run_completed`/terminal lifecycle events in the export.**
   Evidence: the real sample projects lifecycle `running` and outcome
   `unknown` solely because no terminal event exists in the export.
