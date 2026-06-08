# Ailuros Roadmap

The roadmap is phased to validate the governance thesis incrementally without
premature platformization.

## Product Vision

**Ailuros becomes the governance runtime for AI agents, agentic applications, and
AI-generated software delivery.**

中文：

**Ailuros 成为 AI Agent、Agentic 应用和 AI 交付流程的治理运行时。**

Clarify is the first prototype. EverRun is the second natural scenario.
radarCreation is the third industry scenario.

## Phase 0 - Core Stabilization (v0.1 - finalized)

- [x] In-process runtime orchestration
- [x] Policy-gated tool calls with blocking decisions
- [x] SQLite-backed run timeline
- [x] Path validation
- [x] CLI commands: run show, replay, audit, eval
- [x] Policy file validation
- [x] Framework-neutral adapter contract skeleton
- [x] Refund demo proof

Status: finalized in v0.1.0.

## Phase 1 - Evidence-Only Pipeline (v0.2 - accepted)

- [x] Evidence ingestion from reference-application fixtures into Ailuros timeline
- [x] Timeline export for external evaluation
- [x] Evaluation against stored evidence (non-realtime)
- [x] Regression workflows over evidence sets
- [x] Non-goals preserved: HTTP write API, runtime blocking based on live UI events,
      auth, dashboard, and platformization

Phase 1 is evidence-only. Reference applications send evidence; Ailuros stores,
exports, and evaluates it. No runtime control flows from a browser or external app
into Ailuros in this phase.

## Phase 1.5 - Audit Package MVP (v0.3 - accepted)

- [x] Export audit packages from stored evidence timelines
- [x] Include governance decisions in audit-package outputs
- [x] Provide one deterministic refund-governance demo
- [x] Add v0.3 release smoke check and acceptance tests
- [x] Keep UI, server write API, production integrations, MCP Gateway, broad adapter
      ecosystem, orchestration, and platformization out of scope

## Long-Term Roadmap

The long-term product direction is runtime governance for AI agents. The current
execution focus remains narrow: prove deterministic post-run governance first, then
move toward runtime event ingestion and runtime decisions only after the evidence
contract is stable.

### v1.5 - Post-run Governance Validator

**Status:** Accepted (offline post-run governance validation, five execution packs).

```text
Clarify evidence package
    ↓
Ailuros validation
    ↓
audit decision
```

Value: prove that Ailuros can understand governance evidence.

Execution packs:

| Pack | Scope |
|---|---|
| C-008 | Clarify evidence handoff |
| A-005R1 | Package loader |
| A-005R2 | Timeline contract validator |
| A-005R3 | Minimal governance decision |
| A-006R | Markdown audit report + demo |

Product message:

**Ailuros v1.5 validates Clarify governance evidence and produces a deterministic
post-run audit decision.**

中文：

**Ailuros v1.5 能验证 Clarify 的治理证据，并生成确定性的运行后审计决策。**

### v2.0 - Runtime Event Ingestion

```text
Clarify runtime
    ↓ HTTP
Ailuros ingestion API
    ↓
event store
```

Value: move from offline evidence packages to realtime governance event ingestion.

Boundary: Ailuros receives events only. It does not block runtime behavior in v2.0.

### v2.5 - Runtime Decision API

```text
Clarify before risky action
    ↓
Ailuros decision API
    ↓
allow / warn / review / block
```

Value: Ailuros starts influencing runtime behavior. This is the key product turning
point where Ailuros begins to act like a governance runtime.

### v3.0 - Policy + Audit Loop

```text
events
  ↓
policy evaluation
  ↓
risk scoring
  ↓
audit report
  ↓
release gate
```

Capabilities:

- Policy packs
- Constitution rules
- Human review
- Release readiness
- Regression baseline

Value: Ailuros becomes the AI delivery governance layer.

### v3.5 - Replay + Regression Governance

```text
old run evidence
new run evidence
    ↓
Ailuros compares behavior
    ↓
regression / drift / risk report
```

Value: Ailuros governs behavior change, not only individual runs.

Applies to:

- Clarify
- EverRun
- AI coding agents
- Document analysis agents
- Enterprise workflow agents

### v4.0 - Multi-Agent Governance Runtime

```text
planner agent
coder agent
judge agent
tool agents
business agents
    ↓
Ailuros governance runtime
```

Capabilities:

- Agent identity
- Tool permission
- Decision trace
- Cross-agent audit
- Escalation
- Risk memory

Value: enterprises can understand what AI agents did, why they did it, who approved
it, and where the risk lives.

### v5.0 - Governance Standard / Marketplace Layer

Future direction:

- Ailuros governance contract
- Ailuros policy packs
- Ailuros-compatible agents
- Ailuros audit packages

This layer can eventually connect with AILUC and an MCP marketplace.

Value: Ailuros defines a trusted operating standard for AI agents rather than only
selling a tool.

Boundary: this is distant vision, not current execution scope.

### Phase 5 Deferral

Phase 5 is deferred to v0.4+.

It remains explicitly deferred from the current release scope.

## Product-Line Positioning

| Product | Role in the Ailuros system |
|---|---|
| Clarify | First governed app prototype |
| EverRun | AI coding agent governance scenario |
| radarCreation | Enterprise risk-monitoring agent scenario |
| MCP Gateway | Tool integration and observation entry point |
| Ailuros | Governance runtime / audit brain |

Core narrative:

**Ailuros is the governance runtime. Clarify, EverRun, and radarCreation are
governed agentic applications. MCP Gateway is one of the tool/event entry points.**

## Current Boundaries

Do not build these in v1.5:

- Runtime blocking
- Complex policy DSL
- Multi-agent registry
- Marketplace integration
- Dashboard
- Database-heavy platform
- Enterprise permission model

These are vision-level capabilities, not v1.5 work. The immediate job is to tighten
the first proof: deterministic validation of Clarify governance evidence.

## Timeline Notes

- Versions are sequential but may overlap at boundaries.
- No phase introduces a core dependency on any reference application.
- v1.5 starts from the accepted v0.3 audit-package baseline.
- The final target is not an evidence package; the final target is runtime
  governance for AI agents.
