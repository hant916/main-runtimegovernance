# Phase 1 Readiness

**Date:** 2026-06-04

## Status

Phase 1 (Clarify Evidence Integration) is defined and scoped at the
documentation level. No integration code has been implemented in this
repository.

## Evidence-Only Boundary

Phase 1 is **evidence-only**. Clarify sends structured evidence records into
the Ailuros runtime timeline. Ailuros stores, exports, and evaluates that
evidence. No runtime control flows from the browser into Ailuros; no governance
decisions flow back to Clarify.

This contract defines release/readiness evidence expectations only. It does not introduce an automatic evidence-only review mode, does not bypass governance decisions, and does not change runtime acceptance rules.

## Core Invariants

Ailuros remains:
- **Application-agnostic** — no browser, domain, or reference-app concept
  enters `src/ailuros/`.
- **In-process** — no server, HTTP write API, or remote governance endpoint.
- **Framework-neutral** — the adapter contract skeleton is in place; no
  LangChain, LlamaIndex, or MCP adapter is implemented in this phase.

## App-to-Core Relationship

Clarify is a **reference application** and **proof path**, not a peer core.
It validates the governance thesis with real-world evidence ingestion but does
not drive or redefine Ailuros core contracts or schema.

## Exclusions

The following are explicitly deferred from Phase 1 and forbidden in this pack:

- HTTP write API or auth system
- Browser runtime coupling (realtime blocking from UI events)
- Clarify-defined core schema mutation
- Dashboard, UI platform, or observability frontend
- Phase 5 platformization features (multi-tenant server, REST API, adapter
  ecosystem, PyPI publishing)

## Readiness Checklist

- [x] Phase 1 contract documented in `docs/contracts/phase1-evidence-only-contract.md`
- [x] Evidence payload expectations defined at the contract level
- [x] Explicit deferrals documented for HTTP write API, auth, dashboard,
      browser blocking, and platformization
- [ ] Evidence ingestion implementation (Phase 1 code) — deferred to future
      integration pack
- [ ] Timeline export from stored evidence — deferred
- [ ] Evidence-based evaluation — deferred

## Dependencies

- [ADR-0003: Evidence-First Integration](docs/decisions/ADR-0003-evidence-first-integration.md)
- [Clarify Reference Architecture](docs/architecture/clarify-reference-architecture.md)
- [Phase 1 Evidence-Only Contract](docs/contracts/phase1-evidence-only-contract.md)
- [Roadmap](docs/strategy/roadmap.md)
