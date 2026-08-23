# EverRun Dogfood Operations

Operating procedure and product acceptance checklist for the Ailuros EverRun
dogfood deployment. This MVP is post-run and evidence-first: Ailuros observes
completed runs; it does not control EverRun while a run is executing.

---

## T1: Package Intake

### Evidence Package as the Only Handoff

EverRun writes a canonical evidence package to disk after each run completes.
The package is the **sole handoff** from EverRun to Ailuros. No streaming API,
no shared database, no side-channel delivery.

An evidence package is a directory containing:

- **`manifest.json`** — package metadata (source, schema_version, run_id, list of files,
  optional provenance and pkg_metadata)
- **`timeline.json`** — ordered timeline events (`schema_version`, `run_id`, `events[]`)

Each event contains `event_id`, `event_type` (free-form string), `timestamp`,
`payload`, and optional `metadata`.

Package loading and ingestion live in:

| Step | Function | Module |
|---|---|---|
| Load | `load_evidence_package()` | `ailuros.adapters.evidence_package.loader` |
| Ingest | `ingest_evidence_package()` | `ailuros.adapters.evidence_package.ingest` |
| Validate contract | `validate_evidence_package_contract()` | `ailuros.adapters.evidence_package.validator` |

### Historical Baseline Procedure

For a bounded historical dogfood baseline, use the fixed selection and result
format in `docs/dogfood/everrun-history-baseline.md`. Record stable run IDs,
native controller facts, the Ailuros-derived result, the separately stated human
expectation, and an evidence reference only. Do not commit `.everrun/history`,
raw runtime artifacts, logs, or generated reports.

Controller history is not itself an evidence package. Do not import it directly
or transform missing facts into a clean result. Until a lossless,
privacy-screened `runtime-evidence-package-v1` export exists, record the
Ailuros judgment as `unknown` / not evaluated and classify it as an expected
unknown when the input is insufficient. This procedure is post-run documentation
only; it does not change ingestion, projection, governance decisions, or
runtime control semantics.

### Historical Baseline Convergence (8051)

The 8051 re-run of the fixed ten-run baseline confirms the same input boundary
after external-evidence projection normalization (8048) and the governance
regression delta read model (8050). When a selected history record has no
canonical package, do not invoke package load, ingest, rebuild, or report on
the history directory. Record `unknown` / not evaluated as an expected unknown
instead; this is neither a pipeline failure nor a new BLOCKED or HUMAN_REVIEW
path.

`compare_governance_projections()` is applicable only after both baseline and
current inputs have produced `ExecutionProjection` objects. It cannot turn a
non-package historical input into a projection or a clean result. The detailed
ten-row comparison and bounded acceptance decision are recorded in
`docs/dogfood/everrun-history-baseline.md`.

### Historical Baseline Convergence (8064)

The 8064 re-run records the final convergence for the external
governed-execution boundary after packs 8052-8063. It re-evaluates the same
bounded real EverRun evidence and classifies each prior finding as fixed,
still-open, expected-unknown, or newly-discovered. The full classification,
responsible-pack mapping, and acceptance record are in
`docs/dogfood/everrun-history-baseline.md`.

When the referenced run identifier (`run-20260822-180944`) is unavailable
locally, the pack documents the exact unavailability and uses an equivalent
real EverRun export that carries the same conflict class
(`run-20260823-033016`), copied faithfully into a conformant
`ailuros.timeline.v1` package with all events unchanged. This is a documented
replay artifact only; it is not a new evidence package, a governance change,
or a new BLOCKED / HUMAN_REVIEW path.

The production path is executed on the faithful copy:
`evidence-audit` → `import-evidence-package` (or `batch-import`) →
`report RUN_ID --rebuild`. Key acceptance checks repeated in this re-run:

- Cross-scope decision differences (`accept` vs `continue`) produce **no**
  `evidence_inconsistency` signal; same-scope contradictions remain detectable.
- Review-required scopes remain visible at the aggregate governed-outcome
  level; an `unknown` governed result is never promoted to clean.
- Lifecycle, native outcome, governed outcome, coverage, scoped signals,
  temporal attribution, and evidence refs are recorded separately.
- Raw `.everrun/history`, generated reports, and runtime artifacts are **not**
  committed.

### Validate, Then Import a Single Package

Validate the completed package before it enters storage:

```bash
python -m ailuros evidence-audit PATH/TO/PACKAGE_DIR --format json
```

This validates the evidence contract and renders a post-run pass/warn/fail
result without changing the database. A `fail` result must be investigated;
the operator must not treat a warning as a clean acceptance.

After a package is acceptable for dogfood analysis, import it:

```bash
python -m ailuros import-evidence-package PATH/TO/PACKAGE_DIR
```

Imports the package into the local SQLite store. The importer parses the
package before storage; run `evidence-audit` first for full contract
validation. It returns JSON with `status`:
- `created` — new events stored
- `already_present` — idempotent re-import; no duplicate events
- `conflict` — event ID exists with different content (SHA-256 mismatch)

Single-package import preserves raw evidence only; it does not create a
projection. Rebuild the run before requesting a report.

### CLI: Batch Import

```bash
python -m ailuros batch-import PATH/TO/PACKAGES_ROOT
```

Discovers child directories containing both `manifest.json` and `timeline.json`,
loads each, ingests events, rebuilds projections and signals. Returns a
`BatchSummary` JSON with `total`, `created`, `already_present`, `invalid`,
`conflict`, `projected`, `projection_failed`, and `failures[]`.

### Idempotency

- `ingest_evidence_package()` checks for existing runs and matching event hashes
  before inserting. Re-running import with the same package produces
  `ALREADY_PRESENT`.
- `rebuild_projections_and_signals()` is deterministic: same events produce same
  projection and same signals.
- Projection upsert (`upsert_projection`) and signal replacement
  (`replace_signals`) are overwrite-safe.

### CLI: Audit a Package Without Importing

```bash
python -m ailuros evidence-audit PATH/TO/PACKAGE_DIR [--format json|md] [--out FILE]
```

Validates the package against the evidence contract and produces a pass/warn/fail
audit result. Does not modify the database. Use this for pre-import checks or
ad-hoc validation of packages from disk.

---

## T2: Projection / Rebuild

### Derived Tables Are Disposable

The `projections` and `signals` tables contain **derived data only**. Raw
evidence (stored as `RuntimeEvent` rows in the events table) is the source of
truth. Projections and signals can be dropped and rebuilt at any time without
data loss.

| Table | Content | Rebuildable |
|---|---|---|
| `events` | Stored evidence (raw) | No — persisted once |
| `projections` | `ExecutionProjection` per run | Yes |
| `signals` | `GovernanceSignal` per run | Yes |

### How to Rebuild Without Touching Raw Evidence

`rebuild_projections_and_signals()` in `ailuros.projection`:

1. Lists all events for the run from storage
2. Calls `build_execution_projection()` to derive lifecycle, outcome, validation,
   scope, decisions, roles, changes
3. Calls `derive_signals()` to produce governance signals
4. Upserts projection into `projections` table
5. Replaces signals in `signals` table (clears previous)

### CLI: Report with Rebuild

```bash
python -m ailuros report RUN_ID --rebuild [--format json|md]
```

With `--rebuild`, regenerates the projection and signals from stored events
before rendering the report.

### CLI: Programmatic Rebuild

To rebuild programmatically, call `rebuild_projections_and_signals(storage,
run_id)` from an operator script:

```python
from ailuros.projection import rebuild_projections_and_signals

projection, signals = rebuild_projections_and_signals(storage, run_id)
```

Signals returned are the same `GovernanceSignal` objects stored in the DB.

### Projection Fields

| Field | Type | Meaning |
|---|---|---|
| `lifecycle` | `running / completed / failed / unknown` | Inferred from `run_started`, `run_completed`, `run_failed` events |
| `outcome` | `success / partial / blocked / review_required / failed / unknown` | Derived from governance decisions (block=BLOCKED, require_review=REVIEW_REQUIRED); falls back to lifecycle |
| `validation` | `passed / failed / partial / not_run / unknown` | Aggregated from `project_validation` events |
| `scope` | `clean / violated / unknown` | Aggregated from `project_scope` events |
| `decisions` | `DecisionSummary[]` | Each decision includes `domain`, `decision`, and `projected_domain` (`runtime_action`, `execution_control`, `post_run_audit`, `source_preserved_unknown`) |

---

## T3: Product Usage

### Operator Flow: Run Report → Overview → Problems → Evidence

Use the Console against the read-only Ailuros server for the cross-run product
flow. Start the server with the dogfood SQLite database, then open the Console
configured to use that server:

```bash
python -m ailuros --db PATH/TO/ailuros.sqlite server
```

1. **Run Report** — open a run detail to inspect lifecycle, outcome,
   validation, scope, decisions, signals, and the report's evidence index. The
   equivalent operator command is `python -m ailuros --db DB report RUN_ID`.
2. **Overview** — select the time window and optional `everrun` source in the
   Console's Overview view. It reads `GET /analytics/overview`; both
   `window_start` and `window_end` are required ISO-8601 timestamps with a
   timezone.
3. **Problems** — select the same filters in the Console's Problems view. It
   reads `GET /problems`, which groups signals by type and subject. Choose a
   problem to view its contributing signals at
   `GET /problems/{signal_type}/{subject_key}`.
4. **Evidence drill-down** — use each contributing signal's `evidence_refs` or
   the run report's Evidence Index to identify the originating event. Export
   the stored raw events with `python -m ailuros --db DB evidence RUN_ID
   --output json` and match the reference to its event ID.

The Console is read-only. It renders product views; it does not mutate evidence
or infer governance status locally.

### Overview Dashboard

`build_fleet_overview()` in `ailuros.analytics` aggregates across all runs in a
time window:

```python
from ailuros.analytics import build_fleet_overview
from datetime import datetime, timedelta, timezone

storage = open_storage()
window_end = datetime.now(timezone.utc)
window_start = window_end - timedelta(days=7)
overview = build_fleet_overview(storage, window_start, window_end, source="everrun")
```

Returns a `FleetOverview` with:
- `total_runs`, `outcomes` (by type), `validations` (by type), `scopes` (by type)
- `sources` (by source label), `fallback_count`, `fallback_rate`
- `signals` (count by signal type)

### Run Report

```bash
python -m ailuros report RUN_ID [--format json|md]
```

Produces a deterministic per-run governance report:

1. **Headline** — `run_id`, `lifecycle`, `outcome`, `validation`, `scope`
2. **Why Stopped** — human-readable reason (priority: execution_control block >
   review_required > blocked > lifecycle+signals > signals > unknown)
3. **Timeline** — started_at, completed_at, step_count, decision_count, event_count
4. **Decision Reasons** — each governance decision with domain, decision, projected_domain
5. **Signals** — each governance signal with type, severity, subject, evidence_refs
6. **Changes** — files touched (from `project_scope.changed_files`)
7. **Roles** — runtime roles detected
8. **Evidence Index** — event_id → artifact/pointer links

### Optional Repeated-Run Governance Delta

For repeated EverRun dogfood runs, operators may compare two already-built
`ExecutionProjection` objects with the source-neutral read model:

```python
from ailuros.regression import compare_governance_projections

delta = compare_governance_projections(baseline_projection, current_projection)
for dimension in delta.dimensions:
    print(dimension.dimension, dimension.transition)
```

The delta reports native and governed outcomes, validation, scope,
authority/approval/budget facts, and their coverage. It labels unknown inputs
as `unknown` and semantic changes without an ordering as `incomparable`; it
does not infer a risk score. This is a post-run comparison aid only: it does
not write evidence, modify a projection, block a release, or create a new
runtime control or review path.

### Problem Aggregation

`aggregate_problems()` in `ailuros.problems` groups signals by `(type, subject)`
for the Console's `GET /problems` endpoint and returns `ProblemGroup` entries
with:
- `count`, `affected_run_ids`, `first_seen`, `last_seen`
- `severity_counts` (critical/high/medium/low breakdown)
- `trend_buckets` (daily counts from first_seen to last_seen)

### Evidence Drill-Down

From a `ProblemGroup`, call `get_problem_detail()` to get `ContributingSignal`
entries. Each contribution has:
- `signal_id`, `run_id`, `severity`, `evidence_refs`, `created_at`

From a `RunReport`, use `evidence_refs` to trace back to stored events via the
`evidence` CLI:

```bash
python -m ailuros evidence RUN_ID [--output json|jsonl]
```

Returns stored evidence events with full payloads. Use evidence event IDs from
signal/decision evidence_refs to locate the triggering event.

### Meaning of `unknown` / No-Signal

| State | Meaning | Action |
|---|---|---|
| `lifecycle: unknown` | No `run_started` event found | Check if package is truncated or malformed |
| `outcome: unknown` | No blocking/review decision AND lifecycle is RUNNING or UNKNOWN | Run may still be in progress or package is incomplete |
| `validation: unknown` | No `project_validation` events | Package may pre-date validation pipeline or validation was skipped |
| `scope: unknown` | No `project_scope` events | Package does not contain scope projection events |
| No signals at all | `derive_signals()` returned empty list; no rules triggered | Clean run: no failures, no scope violations, no inconsistencies detected |

An empty signal list for a run with `lifecycle: completed` and
`validation: passed` is **normal** — it means the current deterministic signal
rules found nothing to flag. It is not proof that every possible governance
control was evaluated.

A run with `lifecycle: unknown` and `outcome: unknown` and no signals means the
package provided insufficient events for the projection to derive facts.

---

## T4: Deferred Phases

The following features are **not part of the current MVP**. They are documented
as known exclusions to set expectations for the dogfood scope.

| Feature | Status | Notes |
|---|---|---|
| **Realtime event ingestion** | Deferred | MVP imports packages post-run from disk. Streaming or event-by-event ingestion requires a runtime API not present today. |
| **Runtime decision API** | Deferred | MVP does not call back into EverRun to gate tool calls. Governance is post-run audit only. |
| **LLM explanation** | Deferred | Reports are deterministic rule outputs. No LLM-generated summaries, interpretations, or recommendations. All governance decisions cite contract rules and observed evidence. |
| **Multi-tenant SaaS** | Deferred | Single SQLite database per deployment. No tenant isolation, no cloud API, no auth layer. |
| **ClickHouse / OTel scale-out** | Deferred | Data lives in a local SQLite file. No distributed metrics, traces, or columnar analytics store. |
| **Historical trend analysis** | Deferred | `FleetOverview` aggregates within a time window only. No persistent aggregation, no trend storage, no time-series dashboards. |
| **Live tool call gating** | Deferred | No runtime control surface from Ailuros back to EverRun. Governance is observe-only. |

For the data flow context, see `docs/architecture/everrun-dogfood-data-flow.md`.

### Framework Neutrality: Second-Producer Conformance

"No Framework Left Behind" is a product claim, not just an EverRun feature.
`tests/test_second_producer_conformance.py` and
`fixtures/runtime-evidence/second-producer/` prove this with a second,
non-EverRun producer (a generic MCP-style workflow fixture) that traverses
the identical load/ingest/projection/signal/governed-outcome code path as an
EverRun package, using the same `runtime-evidence-package-v1` contract. Core
governance modules (`ailuros.projection`, `ailuros.signals`,
`ailuros.execution_report`) contain no producer-identity branching; a static
anti-regression test guards against reintroducing one.

Only one adapter shape is exercised: the evidence-package (post-run, disk-based)
handoff. A real external integration (LangGraph, OpenAI Agents SDK, an MCP
server, etc.) that emits this contract remains deferred — this pack proves
the contract is producer-neutral, not that additional producer integrations
exist today.

Imported packages are stored as `RuntimeEventType.EXTERNAL_EVIDENCE` wrappers.
At the projection boundary, `build_execution_projection()` reads the embedded
original `event_type`, object `payload`, and metadata through a copied event
view. This restores lifecycle and governance projection for EverRun and
second-producer packages without changing raw evidence, ingestion idempotency,
or conflict detection. Malformed wrappers remain unprojected rather than being
inferred as canonical governance events.

---

## Product Acceptance Checklist

Use this checklist for each dogfood acceptance session. Record the package path,
run ID, database path, and observation outside this repository; do not commit
runtime evidence or generated reports.

- [ ] A completed EverRun run produced one canonical evidence package containing
  `manifest.json` and `timeline.json`; no alternate handoff was used.
- [ ] `evidence-audit` was run against that package and any `warn` or `fail`
  result was reviewed rather than accepted as a pass.
- [ ] `import-evidence-package` or `batch-import` returned `created`, or a repeat
  of the identical package returned `already_present`; no `conflict` was accepted.
- [ ] The run was rebuilt with `report RUN_ID --rebuild`, and the report showed
  the expected lifecycle, outcome, validation, scope, decisions, and signals.
- [ ] Rebuilding changed only derived `projections` and `signals` data; stored
  evidence remained the basis for the rebuilt result.
- [ ] The Console's Run Report, Overview, and Problems views loaded for the
  selected time window and source without client-side status interpretation.
- [ ] Each displayed problem could be traced through `evidence_refs` to a
  stored evidence event for its run.
- [ ] Unknown and no-signal states were interpreted as documented above and
  were not represented as a universal success claim.
- [ ] The acceptance claim is limited to this MVP; it does not imply realtime
  ingestion, runtime gating, LLM explanations, multi-tenant SaaS, or
  ClickHouse/OTel scale-out.
