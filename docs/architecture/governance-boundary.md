# Governance Boundary: App / Core Separation

This document defines the boundary between Ailuros core and any application (reference
or otherwise) built on top of it. Violations are coupling red lines.

## Core Domain (`src/ailuros/`)

The Ailuros core owns:

- Governance runtime lifecycle (start, complete, tool wrap).
- Policy evaluation and blocking decisions.
- Run timeline storage and retrieval.
- Path validation.
- CLI commands.
- Policy file validation.
- Adapter contract interfaces.

Ailuros does **not** own the model agent loop, subagents, schedulers, or the
coding execution workflow. Those belong to the execution plane (e.g. EverRun or
another harness). Ailuros provides governance/control-plane semantics plus
optional enforcement points; it is not an agent orchestrator. See
ADR-0005 for the frozen control-context boundary.

## Governed Execution Boundary

Ailuros governs **executions over time**, not identities, sessions, or orchestration.
The canonical governance subject is a governed execution identified by a run plus an
optional producer-neutral execution scope reference.

Ailuros may receive and preserve opaque references such as:

- `principal_ref`
- `workflow_ref`
- `invocation_ref`
- `policy_snapshot_ref`
- `scope_ref`

These references are correlation and governance-attribution inputs. They are not
credentials, IAM roles, session handles, workflow-engine objects, or runtime-specific
execution objects.

`scope_ref` exists only to distinguish independently governed execution scopes inside
a larger run. Producers may map their own concepts to it, for example a task, node,
pack, tool call, or other execution unit, but Ailuros core must never encode those
producer-specific concepts directly.

The core rule is:

> Ailuros governs facts and decisions about an execution scope; it does not own the
> mechanism that schedules, retries, routes, or executes that scope.

## External Boundary Surfaces

Ailuros has four explicit boundary surfaces.

### 1. Evidence ingress

External runtimes provide execution facts and evidence. Ailuros accepts producer
facts, preserves provenance, and normalizes only what the canonical contracts support.
Unknown evidence must remain source-preserved unknown rather than being reinterpreted
into a clean or authorized state.

### 2. Governance-context ingress

External systems may provide opaque identity, invocation, policy, authority, approval,
budget, and scope references. Ailuros may use them to correlate governance evidence,
but it does not become the system of record for IAM, authentication, workflow state,
or approval UX.

### 3. Governance-decision egress

Ailuros may produce governance decisions such as allow, warn, review, or block.
The execution plane remains responsible for enforcing or operationalizing those
decisions. Ailuros does not execute the business action itself.

### 4. Governed-outcome and audit egress

Ailuros owns deterministic governance judgments derived from preserved evidence,
including governed outcome, signals, coverage, provenance, replay, and regression
views. These outputs must remain explainable through evidence references.

## Product Ownership Matrix

| Capability | Owner |
|---|---|
| Authentication / login / tokens | External IAM / gateway |
| Users / groups / RBAC | External IAM |
| MCP routing / tool discovery | Runtime / gateway |
| Agent planning / scheduling | Execution runtime |
| Retry / fallback / model routing | Execution runtime |
| Workflow execution | Execution runtime |
| Opaque execution references | External producer supplies; Ailuros preserves |
| Delegated authority judgment | Ailuros |
| Policy snapshot attribution | Ailuros |
| Approval continuity / constraint judgment | Ailuros |
| Budget constraint judgment | Ailuros |
| Temporal governance judgment | Ailuros |
| Evidence provenance | Ailuros |
| Governed outcome | Ailuros |
| Governance replay / regression | Ailuros |

## Forbidden Coupling

The following are **never** allowed in `src/ailuros/`:

| Category | Examples | Reason |
|---|---|---|
| Browser concepts | Tab, window, navigation, DOM event, content script | Platform-agnostic core |
| Clarify-specific models | CtaField, SidePanelState, ExtensionMessage | Clarify is a reference app, not a core dependency |
| UI state | Active element, hover state, selection range | UI is an application concern |
| Domain-specific entities | Refund request, order, radar track | Domain concepts belong in examples or proof paths |
| Producer execution vocabulary | pack, iteration, planner, coder, LangGraph node, Crew task | Preserve No Framework Left Behind |
| HTTP write API | POST /govern, PUT /policy | Platformization remains deferred |
| Auth / sessions | User token, session ID, login state | Out of scope for the governance kernel |
| Runtime routing | retry engine, backend fallback routing, model selection | Execution-plane responsibility |

## Control-Context Identity References

The fields `principal_ref`, `workflow_ref`, and `invocation_ref` are **opaque
provenance/control references**. They record *who/what initiated and framed a
governed run* for audit and control purposes only.

They explicitly do **not** imply user login, token issuance, a tenant directory,
session resumption, or IAM. They are not credentials and carry no authorization
semantics on their own (ADR-0005).

`policy_snapshot_ref` identifies the policy context attributable to evidence or a
decision. Later policy changes must not silently rewrite earlier governance context.

## Temporal Governance Invariant

A valid governance judgment must be attributable to the evidence and governance
context that applied to the execution scope at the relevant time.

At minimum:

- later evidence must not silently rewrite earlier governance context;
- a later policy snapshot must not be back-applied to earlier actions;
- approval and budget evidence must remain attributable to the scope they govern;
- authority judgments must remain evidence-derived rather than inferred from intent;
- missing or malformed governance evidence must remain unknown rather than becoming
  implicitly allowed, approved, or authorized.

## Allowed Crossings

Boundary crossings must follow these rules:

1. **Ailuros imports nothing from any reference application.** The dependency graph is
   one-way: apps import Ailuros.
2. **Tool functions** live in example code (`examples/`) or in reference app
   repositories. Ailuros provides the `wrap_tool` gate but does not define the wrapped
   functions.
3. **Policy files** are JSON documents loaded at runtime. They reference tool and action
   names but do not import Python modules from Ailuros core.
4. **Evaluation cases** are JSON documents external to core code.
5. **Adapters translate producer formats into canonical evidence.** They must not embed
   producer-specific governance judgments that bypass generic projection and rule
   evaluation.

## Enforcement

- Code review must reject any PR that introduces a reference-app import or
  domain-specific concept into `src/ailuros/`.
- New data types in `src/ailuros/models/` must be application-agnostic.
- If a concept is specific to Clarify, EverRun, radarCreation, LangGraph, CrewAI, or
  another runtime, it belongs in that project's repository, an adapter, or `examples/`,
  never in canonical core semantics.
- Producer conformance tests must prove that unknown evidence and opaque scope refs are
  preserved without inventing governance meaning.
