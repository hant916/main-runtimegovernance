# Product Line Thesis: One Core, Three Proofs

Ailuros is the canonical governance runtime — a single, application-agnostic core that
provides policy-gated tool calls, run timelines, path validation, audit/replay, and
evaluation. Everything else in the product line is a proof, reference application, or
vertical integration built *on top of* Ailuros.

## One Core

**Ailuros** (`src/ailuros/`) is the governance runtime kernel. It owns:

- In-process runtime orchestration (start, complete, tool wrapping).
- Policy evaluation and blocking decisions.
- SQLite-backed run timeline storage.
- Path validation against recorded events.
- Read-only CLI commands (replay, audit, eval).
- Policy file validation.
- A framework-neutral adapter contract for tool wrapping.

Ailuros must remain application-agnostic. No browser, UI, domain-specific, or
reference-application concept belongs in the core.

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
