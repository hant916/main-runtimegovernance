# Clarify Reference Architecture

Clarify is the first governed reference application. It is a browser extension that
ingests web-browsing evidence and submits it to Ailuros for governance evaluation.

This document describes Clarify's relationship with Ailuros at the architecture level.
Clarify implementation details live in the Clarify repository.

## Phase 1 — Evidence-Only Integration

Phase 1 of Clarify integration is **evidence-only**. No runtime control flows from the
browser into Ailuros.

### What Phase 1 Includes

- **Evidence timeline ingestion:** Clarify sends structured evidence records (e.g.,
  web navigation events, user interactions) that Ailuros stores in its run timeline.
- **Timeline export:** Stored evidence can be exported for external analysis.
- **Evaluation:** Evaluation cases can be run against stored evidence timelines.
- **Regression:** Evidence sets can be re-evaluated as policies change.

### What Phase 1 Explicitly Excludes

| Feature | Status | Rationale |
|---|---|---|
| HTTP write API | Excluded | Ailuros remains an in-process library |
| Runtime blocking from browser events | Excluded | No live governance back to Clarify |
| Auth / session management | Excluded | Out of scope for local runtime kernel |
| Dashboard / UI | Excluded | Not a platformization goal |
| Adapter implementation | Excluded | Adapter contract exists but no browser adapter |

## Evidence Model

Evidence records entering Ailuros from Clarify are structured as timeline events. The
event schema is defined in Clarify's repository. Ailuros stores and retrieves events
but does not define browser-specific event types.

```
Clarify Extension
    │  evidence (JSON)
    ▼
Ailuros Timeline  ──► Export / Eval / Regression
```

## Later Phases (Not in Phase 1)

- **Governed LLM call:** Policy gates over LLM-generated content derived from evidence.
- **Runtime control:** Ailuros sending governance decisions back to Clarify for
  enforcement (e.g., blocking a navigation).

## Non-Goals

- Clarify does not become a core dependency of Ailuros.
- Ailuros does not import any Clarify Python module.
- Clarify-specific model types (CtaField, SidePanelState, ExtensionMessage, etc.)
  never appear in `src/ailuros/`.
- No browser-specific concepts enter Ailuros core models.
