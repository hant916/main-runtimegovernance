# Governance Boundary: App / Core Separation

This document defines the boundary between Ailuros core and any application (reference
or otherwise) built on top of it. Violations are coupling red lines.

For the precise canonical contract covering governed-execution semantics, `scope_ref`,
external boundary surfaces, the product ownership matrix, and temporal invariants, see
[governed-execution-scope-v1.md](../contracts/governed-execution-scope-v1.md).
That contract is the authoritative source for what Ailuros owns and does not own at
the execution boundary. ADR-0005 boundaries are preserved in both documents.

For the internal module-level ownership map (which module owns which governance
semantics, and where governance semantics must not be duplicated), see
[canonical-governance-surface.md](./canonical-governance-surface.md).

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

## Runtime-Governance Scalpel

Ailuros is a narrow runtime governance decision/control kernel, not a generic
AI-governance platform. A proposed core capability belongs here only when it
materially improves a proven runtime decision or control boundary. Otherwise it
belongs in a runtime/harness, remains a post-run diagnostic, or stays outside
the product.

Post-run evidence may graduate into runtime control only when all of these are
proven:

1. Repeated production evidence shows a material risk or business need.
2. The required evidence is available before the affected action.
3. The decision semantics are deterministic enough to evaluate, including a
   conservative distinction between unknown and violation.
4. A justified, enforceable intervention point exists.
5. The expected risk or business value warrants the intervention.

Capabilities that fail any criterion remain post-run evidence/diagnostics; a
finding never becomes a runtime gate automatically. When justified, control is
selective and preserves business flow with precise `allow`, `guide`,
`constrain`, `escalate`, or `block` semantics rather than maximum blocking.

The following are outside Ailuros core: generic asset registries and metadata
catalogs, lineage platforms, compliance dashboards or checklists, generic
attestation/cryptographic infrastructure, and connector or plugin zoos.
Authenticity, integrity, or attestation can be context for a governance
decision, but never proves authority or permission by itself.

An external format or context integration requires a concrete producer and
consumer need. Implement that concrete seam first; generalize only after a
second proven case demonstrates a shared abstraction.

## Forbidden Coupling

The following are **never** allowed in `src/ailuros/`:

| Category | Examples | Reason |
|---|---|---|
| Browser concepts | Tab, window, navigation, DOM event, content script | Platform-agnostic core |
| Clarify-specific models | CtaField, SidePanelState, ExtensionMessage | Clarify is a reference app, not a core dependency |
| UI state | Active element, hover state, selection range | UI is an application concern |
| Domain-specific entities | Refund request, order, radar track | Domain concepts belong in examples or proof paths |
| HTTP write API | POST /govern, PUT /policy | Platformization is deferred to Phase 5 |
| Auth / sessions | User token, session ID, login state | Out of scope for local runtime kernel |

## Control-Context Identity References

The fields `principal_ref`, `workflow_ref`, and `invocation_ref` are **opaque
provenance/control references**. They record *who/what initiated and framed a
governed run* for audit and control purposes only.

They explicitly do **not** imply user login, token issuance, a tenant directory,
session resumption, or IAM. They are not credentials and carry no authorization
semantics on their own (ADR-0005).

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

## Enforcement

- Code review must reject any PR that introduces a reference-app import or
  domain-specific concept into `src/ailuros/`.
- `src/ailuros/core/` is a leaf: it imports nothing outside `ailuros.core` and
  `ailuros._compat`. Downstream surfaces (projection, signals, execution report)
  depend on core; never the reverse.
- New data types in `src/ailuros/models/` must be application-agnostic.
- If a concept is specific to Clarify, EverRun, or radarCreation, it belongs in that
  project's repository or in `examples/`, never in `src/ailuros/`.
