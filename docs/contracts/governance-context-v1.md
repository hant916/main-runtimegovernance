# Governance Context Contract v1

**Status:** Accepted

**Date:** 2026-08-15

## Purpose

This contract defines the normative **governance-context** model: a small,
source-neutral set of opaque references that describe *what is being governed*
without importing Ailuros code or imposing any runtime-execution semantics.

The governance context is the shared vocabulary producers use to say:

- **who** the evidence asserts is acting (`principal_ref`),
- **what** body of work is being governed (`workflow_ref`),
- **which** specific invocation boundary is in scope (`invocation_ref`),
- **under which** policy snapshot a decision was made, when known
  (`policy_snapshot_ref`).

Every normalized fact in the context retains evidence references to the
evidence that asserted it. This contract defines **references**, not
identities: all refs are opaque strings and no global identity directory is
required.

## Reference Model

### Opaque References

All governance-context refs are **opaque identifiers**. A consumer MUST treat a
ref as an uninterpreted string and MUST NOT assume structure, resolution rules,
or a shared identity registry. Producers own the encoding and stability of their
refs.

| Field | Type | Required | Purpose |
|---|---|---|---|
| `principal_ref` | str | No | Identifies the actor/principal asserted by evidence (e.g. a user, service account, or agent role). |
| `workflow_ref` | str | No | Groups governed work without defining workflow execution semantics. |
| `invocation_ref` | str | No | Identifies one governed invocation/request/action boundary. |
| `policy_snapshot_ref` | str | No | Identifies the immutable policy/version/hash used for a decision when known. |

None of these refs are required. A producer that cannot assert a given
dimension MUST omit it rather than fabricate a placeholder. Ref presence and
meaning are scoped to the producing source; two different sources MAY use
overlapping ref strings with unrelated meanings.

## Normalized Fact Representation

A `governance_context` is a collection of normalized facts. Each fact has the
following shape:

| Field | Type | Required | Purpose |
|---|---|---|---|
| `field` | str | Yes | One of `principal_ref`, `workflow_ref`, `invocation_ref`, or `policy_snapshot_ref`. |
| `value` | str | Yes | The opaque ref asserted for `field`. |
| `evidence_refs` | list[str] | Yes | One or more producer-native pointers to the evidence that asserted this fact. |

`evidence_refs` are opaque strings. They MAY be event IDs, source pointers,
artifact locators, digests, or other producer-native evidence references. A
producer MUST retain at least one evidence ref for every normalized fact.

```json
{
  "facts": [
    {
      "field": "principal_ref",
      "value": "user:alice",
      "evidence_refs": ["evt-001"]
    },
    {
      "field": "workflow_ref",
      "value": "task:8032",
      "evidence_refs": ["evt-014"]
    }
  ]
}
```

### Ref Scope and Stability

- `principal_ref` scopes to the actor asserted by the evidence, not to an
  external directory. It MAY be a role label (e.g. `coder`, `planner`,
  `reviewer`) but is not limited to any fixed vocabulary.
- `workflow_ref` is a grouping label (e.g. a task, project, or workstream ID).
  It says *this work is part of the same governed body*, and nothing about how
  that work executes.
- `invocation_ref` is the finest boundary: a single request, action, or call
  that was governed. Multiple invocations MAY share one `workflow_ref`.
- `policy_snapshot_ref` points to an immutable policy material. It MAY reference
  producer-native policy (a policy file, a version, or a content hash); Ailuros
  need not store full policy bodies in every evidence package.

## Policy Snapshot Reference

`policy_snapshot_ref` identifies the policy used for a decision **when known**.
It is optional and advisory:

- A ref MAY be a content hash (e.g. `sha256:...`), a version string, or any
  producer-native locator.
- Ailuros consumers MUST NOT require the full policy body to be embedded in an
  evidence package. The ref is sufficient for correlation.
- When a producer does not know which policy snapshot applied, the field is
  omitted. Absence is distinct from "no policy": absence means *unknown*.

## Provenance Rules

Every normalized governance-context fact is **evidence-backed**:

1. **Source pointers required**: each fact MUST retain one or more
   `evidence_refs` that identify the evidence from which the fact was derived.
2. **Contradictions preserved**: when two or more evidence refs assert
   conflicting values for the same dimension, the conflict is preserved as an
   **inconsistency**, not silently reconciled. Producers represent this by
   retaining separate facts with the same `field`, their respective `value`,
   and their respective `evidence_refs`; a consumer MUST surface them rather
   than choosing a winner.
3. **No silent reconciliation**: merging, deduplication, or "latest wins"
   behaviour is out of scope. Any reconciliation is a downstream decision that
   must itself be evidence-backed.

```json
{
  "facts": [
    {
      "field": "principal_ref",
      "value": "user:alice",
      "evidence_refs": ["evt-001"]
    },
    {
      "field": "principal_ref",
      "value": "service:build-bot",
      "evidence_refs": ["evt-014"]
    }
  ]
}
```

## Invariants

1. **Opaque refs only**: governance-context refs are strings with no required
   global directory, registry, or resolution semantics.
2. **Optional, never fabricated**: producers omit refs they cannot assert; no
   placeholder values are required.
3. **Evidence-backed**: every normalized fact carries at least one
   `evidence_refs` entry.
4. **Contradictions are data**: conflicting refs are preserved as
   inconsistencies, never silently merged.
5. **No execution semantics**: `workflow_ref` and `invocation_ref` do not define
   how work executes; this contract defines identification only.
6. **Policy bodies are external**: `policy_snapshot_ref` may point to
   producer-native material; Ailuros need not embed policy bodies.

## Explicit Non-Goals

- This contract does **not** define workflow execution semantics, state machines,
  or orchestration.
- This contract does **not** define a global identity directory or identity
  resolution service.
- This contract does **not** require Ailuros to store or import producer policy
  bodies.
- This contract does **not** make EverRun planner/coder/judge vocabulary
  mandatory; `principal_ref` role labels remain neutral strings.
- This contract does **not** mandate any database migration or runtime
  enforcement. It is a documentation contract only.
