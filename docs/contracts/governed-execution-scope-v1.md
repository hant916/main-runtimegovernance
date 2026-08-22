# Governed Execution Scope Contract v1

**Status:** Accepted

**Date:** 2026-08-23

**Related:** [governance-boundary.md](../architecture/governance-boundary.md),
[governance-context-v1.md](governance-context-v1.md), ADR-0005

---

## Purpose

This contract defines the canonical semantics for a **governed execution** in
Ailuros: what the governance boundary owns, what is explicitly outside it, and
the precise shape of the four external surfaces through which producers interact
with Ailuros governance. It is producer-neutral and must not be interpreted as
an execution model for any specific runtime (EverRun, LangGraph, CrewAI, or
otherwise).

---

## 1. Governed Execution Model

### 1.1 Run

A **run** is the coarsest governance container. It represents one governed unit
of work and is the primary entity around which governance decisions, evidence,
and audit records are organized.

| Property | Value |
|---|---|
| Identified by | `run_id` — an opaque string unique to the producer |
| Lifecycle states | `running`, `completed`, `failed`, `blocked` |
| Governance scope | All evidence, decisions, and outcomes emitted within one run are attributed to that run |
| Producer neutrality | A run does not imply a task, a conversation turn, a planner cycle, an agent loop, or any producer-specific concept |

### 1.2 scope_ref

`scope_ref` is an **optional** opaque string that identifies a finer-grained
governance subject within a run. It allows producers to associate evidence and
decisions with a narrower scope without exposing producer-specific structure to
canonical semantics.

| Property | Value |
|---|---|
| Type | `str \| None` |
| Required | No — producers that cannot assert a scope MUST omit it |
| Semantics | Opaque. No required structure, format, or resolution rules |
| Producer neutrality | MUST NOT be interpreted as a task_id, node_id, pack_id, iteration_id, planner, coder, or judge by Ailuros core |
| Stability | When asserted, a `scope_ref` value MUST remain stable for the duration of the run; producers MUST NOT change it mid-run to re-attribute evidence |
| Absence vs null | Absence means *unknown scope*; it is distinct from an empty or null value |

### 1.3 Producer Vocabulary Boundary

Ailuros canonical semantics contain no EverRun pack vocabulary, no LangGraph
node vocabulary, no CrewAI agent vocabulary, and no other producer-specific
execution model. The following producer terms are **never** canonical in Ailuros
core, regardless of which producer is active:

- `pack_id`, `iteration_id`, `node_id`, `task_id`
- `planner`, `coder`, `judge` (as structural roles beyond opaque `principal_ref`)
- `workflow_graph`, `agent_loop`, `retry_count`, `routing_policy`
- Any producer-specific state machine state label

Producers MAY carry these concepts in evidence payloads under their own
namespaces. They MUST NOT appear as required or optional fields in Ailuros core
models, contracts, or policy evaluation inputs.

---

## 2. External Boundary Surfaces

Ailuros governance interacts with the rest of the system through exactly four
external surfaces. No other crossing points are defined in this contract.

### Surface 1 — Evidence Ingress

**Direction:** Producer → Ailuros

**What crosses:** Structured evidence packages describing actions, tool calls,
or observations that require governance evaluation.

**Constraints:**
- Evidence is accepted as producer-asserted facts. Ailuros does not validate
  producer-internal logic.
- Evidence MUST carry at least one opaque `evidence_ref` traceable to the
  producing source.
- Malformed or unrecognized evidence MUST NOT be treated as implicitly clean or
  allowed. It MUST be preserved as unknown and flagged.
- Evidence ingress is read-only from Ailuros's perspective: accepting evidence
  does not constitute authorization.

**What does NOT cross this surface:** Auth tokens, session state, IAM
credentials, model-routing decisions, retry signals, scheduling directives.

### Surface 2 — Governance-Context Ingress

**Direction:** Producer → Ailuros

**What crosses:** A normalized [governance context](governance-context-v1.md)
— the set of opaque references (`principal_ref`, `workflow_ref`,
`invocation_ref`, `policy_snapshot_ref`, `scope_ref`) that frame *what* is
being governed.

**Constraints:**
- All fields are optional. Producers MUST omit fields they cannot assert rather
  than fabricate placeholders.
- Context refs are opaque strings. Ailuros MUST NOT resolve them against an
  external directory or identity service.
- Context received at the start of a run is **fixed** for that run. Later
  context MUST NOT silently overwrite earlier attribution (see §3 temporal
  invariants).
- Contradictory context refs from different evidence sources MUST be preserved
  as inconsistencies, not reconciled.

**What does NOT cross this surface:** Credentials, login state, session tokens,
IAM roles, policy bodies, execution graphs.

### Surface 3 — Governance-Decision Egress

**Direction:** Ailuros → Producer (caller)

**What crosses:** A governance decision with one of the canonical decision types
(`allow`, `warn`, `sanitize`, `require_review`, `block`, `unknown`) and a
human-readable reason.

**Constraints:**
- Every decision MUST be backed by evidence that crossed Surface 1 or Surface 2.
  Decisions without evidence are prohibited.
- Ailuros MAY emit `unknown` when evidence is insufficient; it MUST NOT emit
  `allow` when evidence is absent or malformed.
- The decision payload does not contain HTTP responses, IAM grants, session
  tokens, or routing directives. It is a governance verdict only.
- Decision delivery mechanism (function return, callback, queue message) is
  chosen by the producer and is outside Ailuros core.

**What does NOT cross this surface:** Action execution, model routing choices,
retry instructions, workflow scheduling, approval tokens, budget authorizations.

### Surface 4 — Governed-Outcome and Audit Egress

**Direction:** Ailuros → Consumer (audit/observability layer)

**What crosses:** Timeline events, decision records, evidence references, and
audit packages that record what happened under governance.

**Constraints:**
- Audit output is **append-only** with respect to a completed run. Records for
  a past run MUST NOT be retroactively modified.
- Audit records MUST include the `run_id` and, when present, the `scope_ref`
  for attribution.
- Evidence referenced in audit output MUST remain traceable to its originating
  producer ref; Ailuros MUST NOT strip evidence refs.
- The audit format is the [Audit Package Contract](audit-package.md).

**What does NOT cross this surface:** Live execution state, mutable runtime
context, credentials, session data.

---

## 3. Product Ownership Matrix

The matrix below defines who is responsible for each concern. "Ailuros" means
the Ailuros governance core (`src/ailuros/`). "Producer" means the execution
plane (EverRun, another harness, or a bespoke integration).

| Concern | Owner | Notes |
|---|---|---|
| IAM / RBAC / auth | **Producer / Identity Layer** | Ailuros receives opaque refs; it does not authenticate or authorize actors |
| API gateway / rate limiting | **Producer / Gateway** | Outside governance core |
| Action execution / tool invocation | **Producer / Runtime** | Ailuros wraps but does not invoke |
| Retry / fallback / scheduling | **Producer / Runtime** | Not a governance concern |
| Model routing / LLM selection | **Producer / Runtime** | Outside governance core |
| Human approval workflow | **Producer / Approval Layer** | Ailuros emits `require_review`; the approval flow is producer-owned |
| Budget enforcement / quota | **Producer / Budget Layer** | Ailuros may emit budget-related decisions; enforcement is producer-owned |
| Policy evaluation | **Ailuros** | Owned exclusively by Ailuros core |
| Governance decision egress | **Ailuros** | Ailuros produces the verdict; delivery mechanism is producer-chosen |
| Evidence ingress and normalization | **Ailuros** | Ailuros normalizes; producers supply raw evidence |
| Governance context normalization | **Ailuros** | Per governance-context-v1 contract |
| Timeline / audit storage | **Ailuros** | Append-only; Ailuros is the store of record |
| Run lifecycle (start/complete/fail) | **Ailuros** | Core owns run state transitions |

---

## 4. Temporal Invariants

These invariants govern how governance attribution is maintained over the
lifetime of a run and how it persists across time.

### 4.1 Policy Snapshot Attribution

- Each governance decision MUST be attributed to the policy snapshot active at
  decision time.
- When `policy_snapshot_ref` is present, the decision record MUST retain it.
- Policy snapshot attribution MUST NOT be rewritten after the decision is
  recorded. A later policy version does not retroactively change a past decision.

### 4.2 Authority Attribution

- The `principal_ref` recorded at the time of evidence ingress is the canonical
  authority for that evidence record.
- Later evidence that asserts a different principal for the same event MUST be
  recorded as a separate fact with its own `evidence_refs`; it does not overwrite
  the original.
- Authority attribution from initial governance-context ingress is frozen for a
  run. Adding a new principal mid-run does not retroactively re-attribute earlier
  evidence.

### 4.3 Approval Attribution

- When a governance decision of type `require_review` is satisfied by a human
  approval signal, the approval MUST be recorded as a distinct event with its own
  timestamp and evidence ref.
- The approval event MUST reference the original `require_review` decision.
- Approval does not modify the original decision record; it is an additive fact.

### 4.4 Budget Attribution

- Budget constraints active at the time of a governed action are attributed to
  that action's evidence record.
- A budget change applied after an action is completed does not retroactively
  re-evaluate or invalidate the earlier decision.
- Budget signals are producer-owned (see ownership matrix); Ailuros records
  budget-related decision reasons as evidence-backed facts.

### 4.5 Evidence Attribution Over Time

- Evidence submitted after a run completes MUST be rejected or flagged as
  out-of-band; it MUST NOT be silently incorporated into the completed run's
  governance record.
- The timestamp recorded in an evidence record is the producer-asserted time of
  the governed event, not the time of ingestion. Both SHOULD be recorded.

### 4.6 Unknown Preservation

- Any evidence, context, or decision type not recognized by the current Ailuros
  version MUST be preserved as-is with outcome type `unknown`.
- Unknown MUST NOT be silently promoted to `allow`, `clean`, or `approved`.
- Unknown records MUST be surfaced in audit output so downstream consumers can
  detect gaps.

### 4.7 Prohibition on Retroactive Context Rewriting

Later governance context MUST NOT silently overwrite earlier governance context
for the same run. Specifically:

- A later `workflow_ref` assertion does not replace an earlier one; both are
  preserved as separate facts.
- A later `scope_ref` does not re-attribute evidence submitted under an earlier
  `scope_ref`.
- Reconciliation of conflicting context, if needed, is a downstream decision
  that MUST itself be evidence-backed and auditable.

---

## 5. Explicit Non-Goals

This contract explicitly does not define:

- How producers implement retry, fallback, or scheduling.
- How approval workflows are built by the approval layer.
- How budget enforcement is implemented by the budget layer.
- Any HTTP API for governance decisions.
- Any policy DSL beyond what exists in the current Ailuros runtime.
- Any producer-specific execution graph, agent loop topology, or node model.
- Any global identity directory or credential store.
- Any mandatory database migration or schema change.

---

## 6. Invariants Summary

| # | Invariant |
|---|---|
| I-1 | `run` is the coarsest governance container; `scope_ref` is an optional, opaque, producer-neutral finer scope |
| I-2 | Producer vocabulary (pack, node, iteration, planner, coder, judge as structural terms) MUST NOT appear in canonical Ailuros core models |
| I-3 | Malformed or unrecognized evidence is unknown, never implicitly allowed or clean |
| I-4 | Governance context received at run start is frozen; later context does not silently overwrite earlier attribution |
| I-5 | Every governance decision is evidence-backed; decisions without evidence are prohibited |
| I-6 | Audit records for a completed run are append-only; retroactive modification is prohibited |
| I-7 | IAM, auth, approval workflow, budget enforcement, retry, model routing, and scheduling are producer-owned, not Ailuros-owned |
| I-8 | Unknown evidence and decisions are preserved and surfaced; they are never promoted to allow/clean |
