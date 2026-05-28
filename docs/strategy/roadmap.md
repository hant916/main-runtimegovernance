# Ailuros Roadmap

The roadmap is phased to validate the governance thesis incrementally without
premature platformization.

## Phase 0 — Core Stabilization (v0.1 — current)

- [x] In-process runtime orchestration
- [x] Policy-gated tool calls with blocking decisions
- [x] SQLite-backed run timeline
- [x] Path validation
- [x] CLI commands: run show, replay, audit, eval
- [x] Policy file validation
- [x] Framework-neutral adapter contract skeleton
- [x] Refund demo proof

**Next:** Polish, hardening, test coverage, and documentation gaps.

## Phase 1 — Clarify Evidence Integration

- [ ] Evidence ingestion from Clarify extension into Ailuros timeline
- [ ] Timeline export for external evaluation
- [ ] Evaluation against stored evidence (non-realtime)
- [ ] Regression workflows over evidence sets
- [ ] **Non-goals:** HTTP write API, runtime blocking based on live UI events, auth,
      dashboard, platformization

Phase 1 is **evidence-only**. Clarify sends evidence; Ailuros stores, exports, and
evaluates it. No runtime control flows from the browser into Ailuros in this phase.

## Phase 2 — Governed LLM Call

- [ ] Policy evaluation over LLM-generated content
- [ ] Tool-call governance for LLM-driven agents
- [ ] Integration with Ailuros policy gate

## Phase 3 — EverRun Loop

- [ ] Continuous-run governance
- [ ] Automated run orchestration
- [ ] Workflow-aware policy evaluation

## Phase 4 — radarCreation Vertical

- [ ] Domain-specific governance rules
- [ ] Vertical integration proof

## Phase 5 — Platformization (future)

- [ ] Multi-tenant runtime server
- [ ] REST API for remote governance decisions
- [ ] Dashboard and observability
- [ ] Adapter ecosystem (LangChain, LlamaIndex, etc.)
- [ ] Full documentation site

This phase is explicitly deferred. Ailuros remains an in-process library until the
governance thesis is validated across multiple proof paths.

## Timeline Notes

- Phases are sequential but may overlap at boundaries.
- Phase 1 starts only after Clarify reference architecture is agreed and this roadmap
  is accepted.
- No phase introduces a core dependency on any reference application.
