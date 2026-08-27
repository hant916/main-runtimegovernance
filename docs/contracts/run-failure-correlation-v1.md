# Run Failure Correlation Contract v1

**Status:** Adopted

**Date:** 2026-08-25

## Purpose

`run_failure_correlation` correlates a **bounded, caller-supplied** set of
canonical run diagnoses and escalates retry guidance when the same structured
runtime/infrastructure failure signature recurs without evidence of a
corrective state change.

It answers one operator question with bounded fields: *is another blind coder
retry still safe, or should we stop and repair the runtime boundary?* It is
**not** long-term memory, monitoring, self-healing, or a multi-agent runtime:
no database, no background worker, no automatic remediation, and no cross-pack
resume loop.

## Inputs

Correlation consumes exactly the finite list supplied by the caller
(`src/ailuros/run_failure_correlation.py`):

- `list[RunDiagnosis]` — canonical diagnoses produced by the 8085
  `run_diagnosis` contract (`src/ailuros/run_diagnosis.py:59`). Each diagnosis
  carries the closed fields `incomplete`, `root_cause`, `root_cause_detail`,
  `next_action`, and `evidence_refs`.

No database, global history directory, repository memory, or background scan
is read to discover additional runs. Any other canonical report surface must be
projected to a diagnosis first (via `diagnose_run`) before correlation.

## Closed Vocabulary

### Failure signature (`FailureSignature`)

A bounded signature derived exclusively from closed diagnosis fields:

- `root_cause` — the root-cause class (`RootCause`).
- `root_cause_detail` — the structured sub-cause code.

Timestamps, run ids, vendor prose, and incidental payload fields are excluded
so equivalent canonical facts yield identical signatures regardless of producer
source labels.

### Recurrence state (`RecurrenceState`)

| Value | Meaning |
|---|---|
| `none` | No failure signatures present. |
| `single` | Failure(s) present but no equivalent signature recurs. |
| `recurrent` | An equivalent structured signature appears in ≥ 2 runs. |
| `unproven` | A run failed without enough structured fields to prove equivalence; recurrence is not matched by prose. |

### Retry safety (`RetrySafety`)

| Value | Meaning |
|---|---|
| `safe` | No recurrence evidence makes a blind coder retry unsafe; per-run diagnoses keep their own actions. |
| `unsafe` | Repeated runtime/process-supervision signature; a blind coder retry is unsafe/ineffective. |
| `unproven` | Recurrence cannot be determined from structured facts. |

### Escalation recommendation

Reuses the bounded `NextAction` vocabulary from run diagnosis. Correlation
returns `repair_runtime` for repeated runtime/process-supervision signatures,
`human_review` when recurrence cannot be proven, and `none` otherwise (per-run
diagnoses remain authoritative). It **never** returns `accept` and never
overrides validation, scope, or acceptance gates.

## Correlation

`correlate_run_failures(diagnoses)` (`src/ailuros/run_failure_correlation.py`):

1. Derive a `FailureSignature` from each diagnosis using only closed fields.
   A diagnosis with no incomplete work, or with an unknown root-cause class,
   yields no signature (its run is listed under `unproven_run_ids` when it
   failed).
2. Group equivalent signatures deterministically (count, run ids, evidence
   refs). `count` is the number of distinct runs carrying that signature.
3. Classify recurrence: `recurrent` iff some signature appears in ≥ 2 runs.
4. Escalate conservatively: when a runtime/process-supervision signature
   recurs, mark retry `unsafe` and recommend `repair_runtime`. Otherwise, when
   a failure could not be signed, surface `human_review`. Otherwise keep
   retry `safe` with no correlation-level escalation.

## Red-line behavior

- **No memory.** Correlation is a pure function over the supplied list. No
  durable memory, history index, database, or background monitor is created.
- **No prose matching.** Signatures are built only from closed structured
  fields. Free-form log similarity and embeddings never determine recurrence.
- **No false correlation.** Different root-cause classes are never conflated,
  and distinct sub-cause codes within the same class are kept separate.
- **No invented cause.** Repeated failure escalates retry safety; it never
  proves an unobserved API/vendor/OOM cause.
- **No automatic action.** Correlation is advisory and read-only. It never
  edits a pack, retries code, repairs the runtime, or returns `accept`.
- **Gates unchanged.** Validation, scope, and acceptance semantics are
  untouched; per-run diagnoses keep their own recommendations.

## Traceability

Every recurrence group carries `evidence_refs` (canonical event identifiers)
plus the matched `run_ids`, so the escalation can be explained as *N equivalent
structured failures at a named layer*.

## Output

- Machine: `render_correlation_json(correlation)` — deterministic JSON with
  `recurrence`, `groups`, `unproven_run_ids`, `retry_safety`,
  `recommendation`, and `recommendation_note`.
- Human: `render_correlation_markdown(correlation)` — recurrence table plus the
  failure-signature groups and advisory note.

## Operator entrypoint

`correlate-failures` (`src/ailuros/cli.py`) is the production-reachable CLI path.
It accepts a finite list of `RUN_ID` arguments plus `--format json|md`, projects
each supplied run to a canonical diagnosis via `diagnose_run`, and correlates the
diagnoses with `correlate_run_failures`. Correlation input is exactly the run ids
supplied on the command line:

- No run discovery. The command reads only the named runs' stored projection and
  signals; it never scans storage for recent or related runs.
- Fail loud. An omitted argument or a nonexistent run id fails the command
  instead of being silently ignored.
- No new surface. It reuses `open_storage`, `ExecutionProjection`,
  `GovernanceSignal`, `diagnose_run`, and the existing correlation renderers; no
  new service, API route, or storage table is introduced.

## Example

Two process-supervision failures with equivalent `unknown` sub-cause across
runs `run-1` and `run-2`:

| Field | Value |
|---|---|
| Recurrence | `recurrent` |
| Recurrence Count | `2` |
| Retry Safety | `unsafe` |
| Recommendation | `repair_runtime` |

A process failure followed by an unrelated scope failure stays `single`/`safe`;
a failed run with an unknown root-cause class reports `unproven` and routes to
`human_review` instead of matching by prose.
