# Runtime Evidence Package Contract v1

**Status:** Accepted

**Date:** 2026-08-08

## Purpose

This contract defines the canonical runtime evidence package v1: a stable,
source-neutral envelope for capturing and transporting evidence records from any
runtime into the Ailuros governance timeline. It encodes no EverRun-specific
fields, no framework-specific core taxonomy, and no central closed enum for
runtime-specific evidence types.

The package is designed to be the **portable unit of evidence exchange** between
a runtime producer and Ailuros governance consumers. It supports post-run
validation, timeline projection, and deterministic identity without requiring
the producer to adopt Ailuros internal abstractions.

## Package Envelope

An evidence package is a directory containing at least one structured
`manifest.json` and one `timeline.json`. Additional artifact files may be
referenced but are never required.

### manifest.json

| Field | Type | Required | Purpose |
|---|---|---|---|
| `source` | str | Yes | Identifies the producing runtime (e.g. `clarify`, `everrun`). Neutral opaque label. |
| `schema_version` | str | Yes | Package schema version; MUST be `"1"` for this contract. |
| `run_id` | str | Yes | Unique run identifier scoped to `source`. |
| `generated_at` | str | Yes | ISO 8601 timezone-aware timestamp of package generation. |
| `metadata` | dict | No | Source-defined key-value metadata. Opaque to Ailuros core. |
| `files` | list[str] | Yes | Ordered list of file paths relative to the package root that constitute the package. MUST include at minimum `manifest.json` and `timeline.json`. |

The `generated_at` field MUST carry a timezone offset (e.g.
`2026-08-08T12:00:00+00:00` or `2026-08-08T12:00:00Z`). Naive timestamps are
rejected.

```json
{
  "source": "clarify",
  "schema_version": "1",
  "run_id": "run-abc123",
  "generated_at": "2026-08-08T12:00:00Z",
  "metadata": {},
  "files": [
    "manifest.json",
    "timeline.json"
  ]
}
```

### timeline.json

| Field | Type | Required | Purpose |
|---|---|---|---|
| `schema_version` | str | Yes | MUST match `manifest.schema_version`. |
| `run_id` | str | Yes | MUST match `manifest.run_id`. |
| `events` | list[dict] | Yes | Ordered sequence of evidence events. |

Every event in the `events` array carries at minimum:

| Field | Type | Required | Purpose |
|---|---|---|---|
| `event_id` | str | Yes | Stable unique identifier for this event within the run. |
| `event_type` | str | Yes | Dotted event type name (see Event Naming Conventions). |
| `timestamp` | str | Yes | ISO 8601 timezone-aware timestamp of event capture. |
| `content_digest` | str | Yes | Deterministic digest of the event payload and type (see Deterministic Identity). |
| `payload` | dict | No | Event-specific structured data. Opaque to Ailuros core. |
| `provenance` | dict | No | Optional event lineage (see Provenance). |

All timestamps in `events[*].timestamp` MUST be timezone-aware. Naive
timestamps are rejected at validation.

```json
{
  "schema_version": "1",
  "run_id": "run-abc123",
  "events": [
    {
      "event_id": "evt-001",
      "event_type": "execution.started",
      "timestamp": "2026-08-08T12:00:00Z",
      "content_digest": "sha256:abcdef...",
      "payload": {},
      "provenance": {}
    }
  ]
}
```

## Provenance

Each event MAY carry an optional `provenance` block providing lineage context.
Provenance is never required and runtimes that lack the relevant dimensions
SHOULD omit the block or leave it empty (`{}`).

| Field | Type | Required | Purpose |
|---|---|---|---|
| `source_event_type` | str | No | The original event type in the producing runtime's vocabulary, when it differs from the canonical `event_type`. |
| `source_artifact` | str | No | The file, resource, or component that produced this event (e.g. `src/tasks.py`, `model:gpt-4`). |
| `source_pointer` | str | No | A runtime-specific locator (e.g. line number, span, span ID). Opaque string. |
| `pack` | str | No | The implementation pack or task identifier that triggered this event. |
| `iteration` | int | No | The iteration or attempt number within the owning context. |
| `role` | str | No | The actor role (e.g. `coder`, `planner`, `reviewer`). Neutral string, no fixed vocabulary. |

All provenance fields are advisory. Validators MUST NOT reject a package
because a provenance field is absent or uses an unrecognised value.

## Governance Context

A package MAY carry an optional `governance_context` block describing *what is
being governed* as opaque references. It is **additive and never required**:
existing producers that omit it remain fully valid, and validators MUST NOT
reject a package because the block is absent.

The block's shape is defined by the [Governance Context Contract
v1](./governance-context-v1.md). In summary:

| Field | Type | Required | Purpose |
|---|---|---|---|
| `principal_ref` | str | No | Actor/principal asserted by evidence. |
| `workflow_ref` | str | No | Grouping of governed work; no execution semantics. |
| `invocation_ref` | str | No | One governed invocation/request/action boundary. |
| `policy_snapshot_ref` | str | No | Immutable policy/version/hash used for a decision, when known. |
| `source_pointers` | list[str] | No | Evidence refs backing the asserted facts. |

All refs are opaque strings; no global identity directory is required.
Contradictory refs are preserved as inconsistency, not silently reconciled.
The block MUST NOT make EverRun planner/coder/judge vocabulary mandatory.

```json
{
  "schema_version": "1",
  "run_id": "run-abc123",
  "events": [],
  "governance_context": {
    "principal_ref": "user:alice",
    "workflow_ref": "task:8032",
    "invocation_ref": "inv:abc123",
    "policy_snapshot_ref": "sha256:9f2c...",
    "source_pointers": ["evt-001", "evt-014"]
  }
}
```

## Event Naming Conventions

Event types use **extensible dotted names** (e.g. `execution.started`,
`tool.called`, `validation.passed`). There is no central closed enum; runtimes
define event types in their own vocabulary.

A small **recommended neutral vocabulary** is provided for interoperability:

### Recommended Event Segments

| Segment | Suggested Meaning |
|---|---|
| `execution` | Run lifecycle events |
| `execution.started` | Run began |
| `execution.completed` | Run finished normally |
| `execution.failed` | Run terminated with error |
| `tool` | Tool invocation events |
| `tool.called` | A tool was invoked |
| `tool.result` | A tool returned a result |
| `validation` | Structural or semantic validation |
| `validation.passed` | Validation check passed |
| `validation.warned` | Validation warning raised |
| `validation.failed` | Validation check failed |
| `decision` | Governance or policy decision events |
| `artifact` | File or artifact production events |

### Rules

1. Event types MUST be non-empty strings using lowercase dotted notation
   (`[a-z][a-z0-9.]*[a-z0-9]`).
2. Event types are opaque to Ailuros core. No central registry defines the
   full set of valid values.
3. Producers SHOULD prefer the recommended vocabulary for segments that match
   their semantics, and extend with their own segments when needed.
4. Unknown event types are preserved as-is. Validators classify them as
   "unknown-preserved" (see Coverage Semantics).

## Deterministic Identity

### Event Identity

Each event's `event_id` MUST be stable across re-materializations of the same
logical event. The recommended construction is a content-addressable identifier
derived from `(run_id, event_type, timestamp, sorted_payload_keys)` via a
deterministic hash (e.g. SHA-256). Runtimes MAY use alternative schemes if they
guarantee stability.

### Content Digest

Each event's `content_digest` enables tamper detection and deduplication
without requiring byte-for-byte payload comparison. The digest MUST cover the
event type and the full payload (not including `event_id` or `provenance`).

The recommended construction:

```
content_digest = sha256(event_type + "\x00" + json_dumps(payload, sort_keys=True))
```

The digest is prefixed with the algorithm name (e.g. `sha256:`). Consumers that
encounter an unsupported digest prefix SHOULD preserve the event but flag a
warning.

## Coverage Semantics

Validators classify each event into one of three coverage states:

| State | Meaning | Trigger |
|---|---|---|
| `recognized` | Event type is known to the recommended vocabulary. | Event type matches a recommended segment exactly or as a recognized extension. |
| `unknown-preserved` | Event type is well-formed but outside the recommended vocabulary. | Event type passes the naming format rule but does not match any recommended segment. Preserved unchanged; generates an informational warning. |
| `malformed` | Event type violates the naming rules. | Event type is empty, contains invalid characters, or does not match the dotted-name format. Produces a validation error. Events with malformed types are still retained in the package. |

Validators MUST NOT reject a package based on coverage state alone. Malformed
event types produce validation errors but the event is preserved; the package
itself remains valid unless other contract violations exist.

## Invariants

1. **Source-neutral**: The contract encodes no runtime-specific vocabulary,
   fields, or semantics. `source` is an opaque label.
2. **No framework-specific core taxonomy**: Event types are free-form dotted
   strings; no closed enum ties this contract to any specific runtime's type
   system.
3. **Time zone discipline**: All timestamps MUST carry a UTC offset. Naive
   timestamps are a schema violation and produce validation errors.
4. **Deterministic ordering**: Events in `timeline.json` are ordered by
   `timestamp` ascending, with stable secondary ordering by `event_id`.
5. **Cross-reference integrity**: `manifest.run_id` MUST equal
   `timeline.run_id`; `manifest.schema_version` MUST equal
   `timeline.schema_version`.

## Explicit Non-Goals

- This contract does **not** define a runtime control API (no allow/warn/block).
- This contract does **not** specify an HTTP ingestion endpoint.
- This contract does **not** prescribe a storage schema or database layout.
- This contract does **not** require any specific producer tooling or SDK.
- This contract does **not** define evaluation, decision, or regression
  semantics — those are separate governance layers.
- Provenance fields are **optional advisory metadata**, not required dimensions
  for every runtime.
