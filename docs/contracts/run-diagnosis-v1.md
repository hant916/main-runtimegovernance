# Run Diagnosis Contract v1

**Status:** Adopted

**Date:** 2026-08-25

## Purpose

`run_diagnosis` projects a deterministic, advisory operator diagnosis from
canonical structured run evidence. It answers exactly four operator questions
with bounded fields:

1. **Incomplete work** — what did not complete.
2. **Root-cause class** — what evidence-backed class is visible.
3. **Current risk** — a small closed risk level for operator display.
4. **Next action recommendation** — an advisory, bounded operator action.

Diagnosis is advisory only. It never edits a pack, widens scope, fabricates
acceptance evidence, or mutates runtime state.

## Inputs

Diagnosis reads only canonical structured facts (`src/ailuros/run_diagnosis.py`):

- `ExecutionProjection` (`src/ailuros/core/execution.py:222`): `lifecycle`,
  `outcome`, `validation`, `scope`, `decisions`, `governance_context`,
  `evidence_refs`.
- `GovernanceSignal` list (`src/ailuros/signals.py:91`): `type`, `severity`,
  `subject`, `evidence_refs`.

No raw console prose, log lines, or producer-specific labels are read. The
projection `source` field is never consulted, which makes diagnosis
source-neutral.

## Closed Vocabulary

### Incomplete work (`IncompleteWork`)

| Value | Meaning |
|---|---|
| `none` | No incomplete work proven. |
| `run_failed` | The run failed (including failed validation). |
| `run_interrupted` | The run is not in a terminal lifecycle. |
| `acceptance_unproven` | Completed but acceptance evidence is missing. |
| `blocked_or_review` | Blocked or review required. |

### Root-cause class (`RootCause`)

| Value | Meaning |
|---|---|
| `execution_runtime/process_supervision` | Process loss/termination at the runtime supervision layer with no governed cause. |
| `scope_boundary` | Scope contamination or attribution violation. |
| `validation` | Proven validation failure. |
| `unproven_completion` | Completion claimed without accepted validation evidence. |
| `pack_definition` | Reserved; a pack-definition defect proven by canonical facts. No current Ailuros canonical fact emits it (structural package validation is a separate concern). |
| `evidence_inconsistent` | Contradictory canonical facts. |
| `unknown` | No closed class applies or cause evidence is insufficient. |

`root_cause_detail` names the explicit canonical sub-cause (for example
`validation_failed`, `approval_denied`, `backend_unavailable`) or stays
`unknown`/`none`.

### Risk (`RiskLevel`)

`low`, `medium`, `high`, `critical`, `unknown`. A single closed level for
operator display; no maturity scoring or multidimensional lens.

### Next action (`NextAction`)

Advisory and bounded to existing operator concepts: `none`, `retry`,
`repair_runtime`, `repair_pack_definition`, `confirm_reconcile`, `stop`,
`human_review`, `inspect`.

## Classification

Classification is precedence-based; the first matching rule wins. Precedence:

1. Evidence inconsistent (signal or `governance_context.inconsistencies`).
2. Scope boundary (signal or `scope == violated`).
3. Validation failure (proven `validation == failed` or signal).
4. Governed stop (authority violation, approval denied, budget exceeded).
5. Review required (human review / approval / budget / authority unknown).
6. Process supervision (`lifecycle == failed`, no governed cause).
7. Unproven completion (`lifecycle == completed`, validation not passed).
8. Non-terminal lifecycle.
9. Clean fallback (no incomplete work, no failure class).

## Red-line behavior

- **No guess.** A process loss with no vendor cause stays
  `execution_runtime/process_supervision` with `root_cause_detail == "unknown"`.
  Rate limiting, OOM, network failure, and vendor outage are never inferred;
  they are named only when an explicit canonical signal proves the class.
- **Missing is not failed.** Missing validation or acceptance evidence maps to
  `unproven_completion` / `acceptance_unproven`, never to `validation`.
- **Scope.** Scope contamination maps to `scope_boundary` and recommends
  `repair_pack_definition` (fix attribution/pack scope evidence). It never
  recommends widening scope or a blind coder retry.
- **Source-neutral.** Relabeling producer source metadata leaves the machine
  diagnosis byte-identical when generated timestamps are fixed.

## Traceability

Every conclusion carries `evidence_refs` (canonical event identifiers) so each
diagnosis decision can be traced without copying raw logs.

## Output

- Machine: `render_diagnosis_json(diagnosis)` — deterministic JSON.
- Human: `render_diagnosis_markdown(diagnosis)` — the four fields plus an
  advisory note and evidence index.
- CLI: `ailuros diagnose <run_id> [--format json|md] [--rebuild]`
  (`src/ailuros/cli.py`).

## Example

A failed run with only a `run_failed` event (no governed cause) yields:

| Field | Value |
|---|---|
| Incomplete | `run_failed` |
| Root Cause | `execution_runtime/process_supervision` |
| Root Cause Detail | `unknown` |
| Risk | `high` |
| Next Action | `retry` |
