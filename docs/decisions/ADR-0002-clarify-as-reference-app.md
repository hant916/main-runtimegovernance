# ADR-0002: Clarify as First Reference Application

**Status:** Accepted

**Date:** 2026-05-29

## Context

Clarify is a browser extension that ingests web-browsing evidence for governance
evaluation. It is the first real-world consumer of Ailuros. Without an explicit
decision, Clarify could become a peer or even the primary project, drawing Ailuros
into browser-specific territory.

## Decision

Clarify is a **reference application** — a proof path that validates the Ailuros
governance thesis with real-world evidence ingestion. It is not a peer core, not the
owner of Ailuros strategy, and not a core dependency.

## Consequences

- Clarify-specific concepts (browser events, CTA fields, side-panel state, content
  scripts) are forbidden in `src/ailuros/`.
- Clarify architecture is documented in this repository only at the reference level
  (`docs/architecture/clarify-reference-architecture.md`).
- Clarify implementation lives in its own repository with its own documentation.
- Ailuros strategy documents are authored in this repository, not in Clarify's.
