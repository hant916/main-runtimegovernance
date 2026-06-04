# Phase 1 Evidence-Only Contract

**Status:** Accepted

**Date:** 2026-06-04

## Purpose

This contract defines the Phase 1 integration boundary between Ailuros and the
Clarify reference application. Phase 1 is **evidence-only** — a unidirectional
feed of evidence records from Clarify into the Ailuros timeline with no runtime
control flow, no HTTP write API, and no platformization.

## Application Agnostic

Ailuros is the canonical governance runtime kernel, not an agent framework, UI
platform, or generic workflow engine. Phase 1 does not change this identity.

- Clarify is a **reference application** and **proof path**, not a peer core.
- Clarify does not define or mutate Ailuros core schema.
- Ailuros remains in-process; no server or platform API is introduced.
- No Clarify Python module is imported by `src/ailuros/`.

## EvidenceRecord Model

The canonical evidence contract is `EvidenceRecord`, defined in
`src/ailuros/models/evidence.py` and exported from `ailuros.models`.

Evidence entering Ailuros is a structured record with an explicit version field:

| Field | Type | Purpose |
|---|---|---|
| `version` | str | Schema version for forward compatibility |
| `run_id` | str | Target run identifier in the Ailuros timeline |
| `event_type` | str | Categorizes the evidence (application-neutral, e.g. `navigation`, `interaction`) |
| `payload` | dict[str, Any] | Opaque event-specific structured data (default `{}`) |
| `timestamp` | datetime | Timezone-aware datetime of evidence capture |

The `EvidenceRecord` is a Pydantic `BaseModel` with `ConfigDict(extra="forbid")`
and follows the same timezone-validation convention as all other Ailuros models.

The payload is opaque to core. Ailuros stores and retrieves evidence records
without validating or interpreting payload contents. Domain-specific payload
shapes are defined by applications (e.g., Clarify) and never appear in
`src/ailuros/`.

The `event_type` field is a free-form string, not restricted to
`RuntimeEventType`. This keeps the contract application-neutral.

## Explicit Deferrals

The following are **out of scope** for Phase 1:

| Feature | Rationale |
|---|---|
| HTTP write API | Ailuros remains an in-process library; Phase 1 uses local ingestion |
| Auth / session management | Out of scope for local runtime kernel |
| Dashboard or UI | Not a platformization goal |
| Realtime browser blocking | No runtime control from browser into Ailuros |
| Clarify-defined core schema | Clarify-specific types never appear in `src/ailuros/` |
| Adapter implementation for Clarify | Adapter contract exists but no browser adapter |
| Phase 5 platformization | Multi-tenant server, REST API, dashboard, adapter ecosystem |

## Scope Boundary

This contract defines release/readiness evidence expectations only. It does not introduce an automatic evidence-only review mode, does not bypass governance decisions, and does not change runtime acceptance rules.

## Acceptance Criteria

1. Phase 1 is documented as evidence-only.
2. No Clarify source code or integration runtime is changed in this repository.
3. Docs preserve the Ailuros core boundary: application-agnostic, in-process,
   framework-neutral.
