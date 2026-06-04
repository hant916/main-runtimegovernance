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

## Versioned Evidence Payloads

Evidence entering Ailuros from Clarify is a structured JSON event with an
explicit version field. The high-level payload expectations are:

| Field | Type | Purpose |
|---|---|---|
| `version` | string (semver) | Schema version for forward compatibility |
| `run_id` | string | Target run identifier in the Ailuros timeline |
| `event_type` | string | Categorizes the evidence (e.g. `navigation`, `interaction`) |
| `payload` | object | Event-specific structured data |
| `timestamp` | string (ISO-8601) | When the evidence was captured |

The event schema beyond these top-level fields is defined in the Clarify
repository. Ailuros stores and retrieves evidence as timeline events but does
not define or validate Clarify-specific payload shapes.

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
