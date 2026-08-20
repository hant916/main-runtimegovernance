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

## Evidence limitations

- The historical controller records provide terminal decisions, validation and
  scope facts when present, but are not the Ailuros evidence-package handoff.
- No history was transformed or backfilled to make absent fields look clean.
- The current post-run ingestion path also has a documented limitation: wrapped
  package event types are not yet unwrapped during projection, which can leave
  lifecycle, outcome, and signals `unknown`; see the known limitation in
  `docs/operations/everrun-dogfood.md` and its conformance coverage in
  `tests/test_second_producer_conformance.py`.
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
