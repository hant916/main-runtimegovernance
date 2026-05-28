# ADR-0001: Ailuros as Governance Runtime

**Status:** Accepted

**Date:** 2026-05-29

## Context

Ailuros started as a proof-of-concept for policy-gated tool calls. As the project
grows, it needs a clear identity: is it a general-purpose agent framework, a policy
engine, or a governance runtime?

## Decision

Ailuros is a **governance runtime** — an application-agnostic kernel that provides
policy-gated tool calls, run timeline storage, path validation, audit/replay, and
evaluation. It is not an agent framework, not a UI platform, and not a general-purpose
workflow engine.

## Consequences

- Ailuros core (`src/ailuros/`) remains focused on governance primitives.
- Browser, UI, and domain-specific concepts are excluded from core.
- Reference applications (Clarify, EverRun, radarCreation) consume Ailuros but do not
  drive its architecture.
- Platformization (server, REST API, dashboard) is deferred until the governance
  thesis is validated.
