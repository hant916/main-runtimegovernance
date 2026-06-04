# Changelog

## v0.1.0 (2026-06-04)

### Governance Core

- In-process `AilurosRuntime` with full lifecycle: `start_run`, `complete_run`, `fail_run`, event recording, and monotonic event sequencing.
- `wrap_tool` — wraps any Python callable with a policy gate; blocked decisions prevent the underlying function from being called.
- `before_tool_call` — records the tool call request, evaluates all loaded policies, resolves the final decision (`ALLOW` / `WARN` / `REQUIRE_REVIEW` / `BLOCK`), and persists the `GovernanceDecision`.
- `validate_path` — compares expected tool-call paths against recorded timeline events.
- `PolicyEngine` — evaluates tool calls against JSON-defined policies; supports 12 operators (`eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`, `exists`, `not_exists`, `contains`, `regex`).
- `DecisionResolver` — priority-ordered resolution from BLOCK through ALLOW, with severity tie-breaking.
- CLI: `policy validate <path>` for policy file validation.

### Runtime Evidence

- SQLite-backed persistence via `SQLiteStorage` — `runs`, `events`, `governance_decisions`, `evaluations`, `audit_reports`, and `replay_runs` tables.
- Thread-safe monotonic event sequencing using `BEGIN IMMEDIATE`.
- Two-level migration system: `001_initial.sql`, `002_indexes.sql`, `003_decision_evidence.sql`.
- 22 `RuntimeEventType` values covering the full governance event taxonomy.
- Paginated `list_runs` and `list_events` with configurable limits.
- CLI: `run list`, `run show <run_id>` with JSON output.

### Evaluation & Regression

- `EvaluationService` — evaluates stored timelines against JSON `EvaluationCase` files with 6 expectation types (governance decision, blocked/allowed tool, tool not executed, path validation, event sequence).
- `RegressionService` — compares evaluation results against a `RegressionBaseline`; detects `pass_to_fail`, `missing_from_current`, and `unexpected_new_fail` regressions.
- `replay_timeline` — validates stored timeline JSON for decision consistency.
- 8 golden evaluation cases in `examples/evaluation/golden.json` covering allow, block, require_review, path validation, tool-not-executed, and event sequence assertions.
- CLI: `eval <run_id>`, `regression compare`, `regression replay`.

### Adapter Contract

- Framework-neutral `RuntimeProtocol` and `ToolAdapter` protocol for external framework integration (LangChain, LlamaIndex, etc.).
- `LocalCallableAdapter` — reference implementation demonstrating the full adapter lifecycle: pre-gate check, tool execution, and result recording.
- `AdapterContext` / `AdapterResult` / `AdapterDecisionStatus` models.
- `ClarifyGovernanceRequest` model for the Clarify reference application governance shape.

### Replay & Audit

- `ReplayService` — read-only timeline loading from storage; does not invoke tools or recompute policy.
- `AuditSummary` / `RunSummary` — derived solely from stored event data.
- `build_audit_report` — combines run summary with event timeline into a complete report.
- CLI: `replay <run_id>`, `audit <run_id>` with JSON output.

### Docs & ADR

- ADR-0001: Ailuros as Governance Runtime (not agent framework, UI, or generic workflow).
- ADR-0002: Clarify as First Reference Application.
- ADR-0003: Evidence-First Integration for Clarify.
- Product strategy: One Core, Three Proofs (product-line-thesis.md).
- Five-phase roadmap with v0.1 core complete (roadmap.md).
- Architecture: governance-boundary.md, clarify-reference-app.md.
- Dogfood: minimal-governance-demo.md validating 5 governance artifacts end-to-end.
