# ADR-0005: Governance Control-Context Boundary

**Status:** Accepted

**Date:** 2026-08-15

## Context

As Ailuros adds control-context evidence fields (see the identity references
below), there is a risk of conflating Ailuros's governance role with
execution-plane responsibilities — the model agent loop, subagents, schedulers,
and coding execution workflow that belong to a harness such as EverRun. Before
any new control-context field is introduced, the boundary must be frozen so the
runtime stays a governance runtime and does not drift into platformizing or
orchestrating the execution plane.

## Decision

### 1. Governance runtime lifecycle vs execution lifecycle

Ailuros may **start and complete governance runs** and **wrap/gate tool calls**.
It does **not** own the model agent loop, subagents, schedulers, or the coding
execution workflow. That lifecycle belongs to the execution plane (EverRun or
another harness).

Wherever the runtime lifecycle is described, the wording is **"governance
runtime lifecycle"**, not wording that implies generic agent orchestration.

### 2. Identity references are opaque provenance/control references

The control-context fields `principal_ref`, `workflow_ref`, and `invocation_ref`
are **opaque provenance/control references**. They identify *who/what initiated
and framed a governed run* for audit and control purposes only.

They explicitly do **not** imply:

- user login,
- token issuance,
- a tenant directory,
- session resumption, or
- IAM.

They are not credentials and carry no authorization semantics on their own.

### 3. Current vs future control

The current 8001-8030 path remains **evidence-first and post-run**: evidence is
captured, stored, projected, and evaluated after the run. This pack does **not**
add a write API or a live enforcement service.

Future runtime decision APIs may consume the same contracts (decision domains,
projections, evidence references) later, but that is a future control surface,
not part of this boundary freeze.

### 4. Ailuros is governance/control-plane semantics plus optional enforcement points

Ailuros provides **governance/control-plane semantics** (policy gating, decision
records, evidence, audit) plus **optional enforcement points** (tool wrapping,
blocking decisions). EverRun and other harnesses remain **execution-plane owners**
and are **independent products** that consume Ailuros.

## Consequences

- Core documentation uses "governance runtime lifecycle" for runtime wording;
  "orchestration" is reserved for execution-plane harnesses.
- `principal_ref`, `workflow_ref`, and `invocation_ref` are documented as opaque
  references, never as auth or session primitives.
- No write API, live enforcement service, auth, session, or IAM is introduced by
  this boundary freeze.
- EverRun and other harnesses remain independent execution-plane products that
  consume Ailuros as a library; Ailuros does not orchestrate them.
