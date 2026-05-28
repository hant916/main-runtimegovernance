# ADR-0003: Evidence-First Integration for Clarify

**Status:** Accepted

**Date:** 2026-05-29

## Context

Clarify requires integration with Ailuros. The integration could take many forms:
evidence-only logging, bidirectional runtime control, live policy enforcement in the
browser, or a full platform API. Premature runtime control risks coupling Ailuros
core to browser-specific event models and deployment complexity.

## Decision

Phase 1 of Clarify integration is **evidence-only**. Clarify sends structured evidence
records to Ailuros for timeline storage, export, evaluation, and regression. No
runtime control flows from the browser into Ailuros (and no governance decisions flow
back to Clarify for enforcement).

## Consequences

- Phase 1 excludes HTTP write API, runtime blocking from browser events, auth,
  dashboard, and adapter implementation.
- Ailuros remains an in-process library; no server or platform API is introduced.
- Evidence schema is defined in Clarify's repository, not in Ailuros core models.
- Later phases may introduce governed LLM call and runtime control, but only after
  evidence-first integration is validated.
