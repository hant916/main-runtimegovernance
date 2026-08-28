# Product Line Thesis: One Core, Three Proofs

Ailuros is the canonical governance runtime — a single, application-agnostic core that
provides policy-gated tool calls, run timelines, path validation, audit/replay, and
evaluation. Everything else in the product line is a proof, reference application, or
vertical integration built *on top of* Ailuros.

## One Core

**Ailuros** (`src/ailuros/`) is the governance runtime kernel. It owns:

- Governance runtime lifecycle (start, complete, tool wrapping).
- Policy evaluation and blocking decisions.
- SQLite-backed run timeline storage.
- Path validation against recorded events.
- Read-only CLI commands (replay, audit, eval).
- Policy file validation.
- A framework-neutral adapter contract for tool wrapping.

Ailuros must remain application-agnostic. No browser, UI, domain-specific, or
reference-application concept belongs in the core.

Ailuros owns the **governance runtime lifecycle** only. It does **not** own the
model agent loop, subagents, schedulers, or the coding execution workflow; those
belong to the execution plane (EverRun or another harness). Ailuros provides
governance/control-plane semantics plus optional enforcement points and remains
an independent product; harnesses that consume it are execution-plane owners and
independent products of their own (ADR-0005).

The control-context fields `principal_ref`, `workflow_ref`, and `invocation_ref`
are opaque provenance/control references, not auth, session, or IAM primitives.

## Product Selection Rule

The product test is simple: if a capability does not materially improve a
proven runtime governance decision or control boundary, it is probably not
Ailuros core. Ailuros owns explainable governance decisions, policy/authority
evaluation, and justified enforcement points; execution orchestration remains
with harnesses such as EverRun.

Post-run findings are evidence, not automatic runtime gates. They graduate only
with repeated production evidence, pre-action evidence availability,
deterministic/evaluable semantics, an enforceable intervention point, and
material risk or business value. This keeps runtime behavior proportionate:
allow, guide, constrain, escalate, or block only when evidence and policy
justify it.

Accordingly, generic registries, asset/metadata catalogs, lineage graphs,
compliance dashboards/checklists, cryptographic attestation infrastructure, and
speculative connector frameworks are not Ailuros core. External systems may
supply context or proof, but integrity or authenticity is never authority or
permission. A format or context adapter begins only with a concrete
producer/consumer need and should remain concrete until repeated evidence
justifies generalization.

See [ADR-0007](../decisions/ADR-0007-runtime-governance-scalpel-boundary.md)
for the durable boundary and graduation rule.

## Three Proofs

The following are **reference applications or proof paths** that consume Ailuros but
never become core dependencies:

| Proof Path | Role | Relationship to Ailuros |
|---|---|---|
| **Clarify** | Evidence-first, governed browser extension | First reference app; validates governance thesis with real-world evidence ingestion |
| **EverRun** | Automated agent-run platform | Proves loop/continuous-run governance on top of Ailuros |
| **radarCreation** | Vertical domain proof | Demonstrates Ailuros applicability in a specific radar/domain context |

These proofs inform Ailuros requirements but do not drive core architecture. Ailuros
defines the platform strategy; the proofs validate it.

## Separation of Concerns

- Ailuros core documentation lives under `docs/strategy/`, `docs/architecture/`, and
  `docs/decisions/` in this repository.
- Each proof path maintains its own implementation repository with its own docs.
- Clarify-specific architecture details appear only in
  `docs/architecture/clarify-reference-architecture.md` (this repository) or in the
  Clarify repository itself.
- No proof-path concept is imported as a Python dependency of `src/ailuros/`.
