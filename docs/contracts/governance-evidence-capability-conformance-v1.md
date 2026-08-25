# Governance Evidence Capability Conformance Contract v1

**Status:** Accepted

**Date:** 2026-08-25

## Purpose

This contract defines capability-level evidence conformance for canonical
evidence packages: a deterministic, source-neutral report of which Ailuros
governance capabilities are **evaluable** from a package's canonical evidence
before import or rebuild.

It answers a narrower question than governance itself: *which governance
capabilities can actually be evaluated from this evidence, which are
unsupported by the producer, and which are missing required evidence?* It is
not a governance decision, not structural package validation, and it never
promotes missing evidence into a clean/pass/success claim.

## Scope

| Concern | Owned here? |
|---|---|
| Structural package validity (`manifest.json` / `timeline.json` contract) | No — reported separately via `package_valid` from the package contract validator |
| Capability evidence sufficiency | Yes |
| Governance judgment (allow/review/block, governed outcome) | No — existing projection/signal semantics remain authoritative |
| Producer identity or framework semantics | No — explicitly inert |

## Capability Matrix (T1)

The minimum canonical evidence required to evaluate each governance capability
is derived from the projection surface: a capability is `evaluable` only when
the package carries the canonical structured events the projection reads to
derive that capability's facts.

An evidence requirement is either a canonical event type (e.g. `run_started`)
or a structured payload reference (e.g. `authority_evidence.payload.actor`).

| Capability | Minimum canonical evidence (any one alternative set) | Reported missing ids |
|---|---|---|
| `lifecycle` | `run_started` **or** `run_completed` **or** `run_failed` | `run_started`, `run_completed`, `run_failed` |
| `outcome` | `run_completed` **or** `run_failed` | `run_completed`, `run_failed` |
| `regression_prerequisites` | `run_started` **or** `run_completed` **or** `run_failed` | `run_started`, `run_completed`, `run_failed` |
| `authority` | `authority_evidence.payload.actor` (non-empty) | `authority_evidence.payload.actor` |
| `approval` | `approval_evidence.payload.subject` (non-empty) | `approval_evidence.payload.subject` |
| `budget` | `budget_evidence.payload.subject` **and** `budget_evidence.payload.unit` (both non-empty) | `budget_evidence.payload.subject`, `budget_evidence.payload.unit` |
| `scope` | `project_scope` | `project_scope` |
| `validation` | `project_validation` | `project_validation` |

The matrix is deterministic and ordered exactly as listed above. A producer is
not required to implement every capability: absent optional governance evidence
yields `missing_evidence`, never package corruption.

## Status Vocabulary

A closed vocabulary, unchanged by the producer:

| Status | Meaning |
|---|---|
| `evaluable` | The package carries at least one full alternative set for the capability. |
| `missing_evidence` | The capability is supported but the package lacks the minimum canonical evidence. Precise missing evidence ids are reported. |
| `unsupported` | Ailuros has no canonical evaluation mechanism for the capability. Never emitted for the standard matrix (all of whose capabilities are supported); reserved for unknown capability ids. |

`unsupported` is distinct from `missing_evidence` (a supported but unevidenced
capability) and from structural invalidity (a package that fails the package
contract validator).

## Deterministic Evaluation (T2)

- Conformance reads only canonical structured events: `event_type` and
  structured `payload` fields from `timeline.json`.
- Source, agent and framework metadata never enters the decision logic.
- Missing evidence is reported as precise identifiers
  (`approval_evidence.payload.subject`), not prose-only reasons.
- A structured payload field counts as present only when it is a non-empty
  string; an empty actor on an `authority_evidence` event does not satisfy
  `authority`.
- The same canonical event set yields the same result regardless of manifest
  source label.

## No-Fabrication Behavior (T4)

- Removing terminal, authority, approval or budget evidence independently
  degrades only the corresponding capability; it never fabricates success.
- Absent authority/approval/budget evidence is never satisfied and never
  converted to clean/pass/success.
- A structurally invalid package reports `package_valid: false` and every
  capability as `missing_evidence` — structural invalidity is never
  manufactured into evaluable statuses.
- Contradictory canonical evidence remains available to downstream
  consistency/governance logic and is never hidden by conformance reporting.

## Result Shape

```json
{
  "package_valid": true,
  "source": "generic-mcp-workflow",
  "schema_version": "ailuros.timeline.v1",
  "run_id": "run-second-producer-001",
  "events_count": 6,
  "capabilities": [
    {
      "capability": "lifecycle",
      "status": "evaluable",
      "missing_evidence": []
    }
  ]
}
```

`package_valid`, `source`, `schema_version`, `run_id` and `events_count` come
from the existing package contract validator and are kept separate from the
per-capability evidence statuses by design.

## CLI Surface (T3)

```
ailuros evidence-conformance <package_dir> [--format json|md] [--out <file>]
```

- Human output (Markdown) identifies capability, status and missing evidence.
- Machine-readable output (JSON) is deterministic: keys are sorted and
  capability order is fixed by the matrix.
- A structurally valid package with missing optional evidence exits zero:
  partial conformance is not a structural failure. A structurally invalid
  package exits nonzero.

## API

```python
from ailuros.evidence_conformance import (
    capability_ids,
    evaluate_evidence_conformance,
    evaluate_capability,
    conformance_result_to_json,
    conformance_result_to_markdown,
)

capability_ids()                     # ("lifecycle", "outcome", ...)
result = evaluate_evidence_conformance(package_dir)
result.package_valid                 # structural validity, separate dimension
result.capabilities                  # [CapabilityConformance, ...]
conformance_result_to_json(result)   # deterministic JSON text
```

## Invariants

1. **Package validity and capability availability are separate dimensions.**
2. **Source-neutral**: relabeling producer metadata leaves the capability
   matrix unchanged.
3. **Deterministic**: the same canonical event set always yields the same
   result.
4. **No fabrication**: missing optional governance evidence yields
   missing/partial semantics, never evaluated success.
5. **Existing governance projections remain authoritative** for actual
   governance judgments.

## Explicit Non-Goals

- This contract is not a governance decision and must not promote `unknown`
  to clean/pass.
- This contract does not require authority, approval or budget evidence to
  exist when the producer does not perform those decisions.
- This contract does not expand the frozen governance semantic surface.
- This contract does not weaken the existing manifest/timeline structural
  validator.
- This contract introduces no producer adapter or plugin registry and no
  `source == everrun` semantic branch.
