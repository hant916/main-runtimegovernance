# ADR-0007: Runtime Governance Scalpel Boundary

**Status:** Accepted

**Date:** 2026-08-28

## Context

Ailuros has proven post-run evidence, projection, diagnosis, and optional
runtime enforcement primitives. Adjacent governance products and standards can
create pressure to accumulate registries, catalogs, dashboards, attestation
infrastructure, and generic connector frameworks that do not improve a runtime
decision. ADR-0005 already freezes execution-plane ownership with runtimes and
harnesses; this decision freezes how Ailuros selects its own core work.

## Decision

Ailuros is a narrow, framework-neutral **runtime governance decision/control
kernel**, not a generic AI-governance platform. A capability belongs in core
only when it materially improves a proven runtime decision or control boundary.

It owns governance decisions, policy and authority evaluation, explainable
decision evidence, and justified enforcement points. It does not own model
loops, planners, schedulers, workflow engines, or other execution-plane
orchestration; those remain runtime/harness responsibilities.

Runtime intervention is selective. It may allow, guide, constrain, escalate, or
block only when policy and evidence justify the precise intervention; it does
not default to maximum blocking.

## Graduation from Post-Run to Runtime Control

A post-run finding may become a runtime capability only when all criteria are
met:

1. Repeated production evidence establishes a material risk or business value.
2. Required evidence is available before the affected action.
3. The decision is deterministically evaluable, including a conservative
   distinction between unknown and violation.
4. An enforceable, justified intervention point exists.
5. The expected value of control justifies its effect on the business flow.

If any criterion is absent, the finding remains a post-run diagnostic or stays
outside Ailuros. No post-run finding automatically becomes a gate.

## Non-Goals and Integration Rule

Generic asset registries, metadata catalogs, lineage platforms, compliance
dashboards/checklists, cryptographic-attestation infrastructure, and connector
zoos are not Ailuros core. Authenticity, integrity, signatures, or attestation
may inform a governance decision but never establish authority, permission, or
policy approval by themselves.

External formats or systems require a concrete producer and consumer need
before implementation. Start with the concrete adapter or seam demanded by that
need; generalize only after a second proven case demonstrates a real shared
abstraction. Market adjacency or standards interest alone is insufficient.

## Consequences

- Current post-run evidence, replay, projection, diagnosis, and bridge behavior
  remain useful evidence paths and are not removed by this decision.
- Future planning must use the graduation criteria and selection rule before
  adding core capabilities.
- No runtime service, database, registry, dashboard, connector, SDK, plugin, or
  generic integration framework is introduced by this ADR.
