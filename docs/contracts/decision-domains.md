# Decision Domain Contract

**Status:** Accepted

**Date:** 2026-08-08

## Purpose

This contract defines the **decision domains** that consumers of Ailuros
governance data encounter. Each domain is a distinct conceptual space with its
own vocabulary, subject matter, and lifecycle. The domains are not unified into a
single enum; they coexist as separate projections over the governance data model.

Consumers choose the domain that matches their question:
- **runtime_action**: was a specific tool/action allowed or blocked by the
  runtime policy engine?
- **execution_control**: what did the source runtime decide about execution flow?
- **post_run_audit**: is the captured evidence package valid after the run?

No implementation is prescribed here. This contract supplies the source-neutral
definitions and mapping guidance only.

## Domain: runtime_action

### Subject

The subject is an **action/tool request** passing through the Ailuros governance
runtime. Every tool call that reaches the policy engine produces a single
governance decision about that call.

### Vocabulary

Uses the existing `GovernanceDecisionType` semantics defined in
`src/ailuros/models/decision.py:10`:

| Value | String | `allowed` | Meaning |
|---|---|---|---|
| `ALLOW` | `"allow"` | `True` | Action may proceed under current policy. |
| `WARN` | `"warn"` | `True` | Action may proceed; a warning is recorded. |
| `SANITIZE` | `"sanitize"` | `False` | Action must not silently proceed; result requires sanitisation. |
| `REQUIRE_REVIEW` | `"require_review"` | `False` | Action must not silently proceed; human review is required. |
| `BLOCK` | `"block"` | `False` | Action is unconditionally rejected. |

These five states are the canonical vocabulary for policy-driven runtime gating
of tool calls. The boolean `allowed` field is the single gate for execution
proceed/block: `True` only for `ALLOW` and `WARN`.

### Decision Record

Every `GovernanceDecision` (`src/ailuros/models/decision.py:18`) is a
runtime_action record. Key fields: `decision_id`, `run_id`, `decision`,
`allowed`, `reason`, `evidence_refs`, `tool_name`, `created_at`.

### Resolution

When multiple policies match the same action, the `DecisionResolver`
(`src/ailuros/policy/decision_resolver.py`) resolves to the single highest-
priority decision: BLOCK > REQUIRE_REVIEW > SANITIZE > WARN > ALLOW.

### Boundary

This domain is exclusively about **one tool call at one point in time**. It does
not cover execution flow control, audit outcomes, or aggregate run-level
judgements.

## Domain: execution_control

### Subject

The subject is the **execution flow** of a runtime. The source runtime (which may
be Ailuros itself or an external runtime controlling an agent loop) produces
decisions that steer the overall run: continue, pause, redirect, or stop.

### Vocabulary

Source runtimes define their own decision vocabularies. Recognised patterns
include:

| Control Pattern | Typical String Values | Description |
|---|---|---|
| Proceed / continue | `"continue"`, `"accept"`, `"proceed"` | Execution may advance to the next step. |
| Partial / limited | `"partial"`, `"limited"`, `"conditional"` | Execution may advance with constraints. |
| Review / escalate | `"review"`, `"require_review"`, `"escalate"` | Execution is paused pending human input. |
| Stop / block | `"block"`, `"stop"`, `"reject"`, `"halt"` | Execution is terminated or prevented. |

### Preserve Source Decision String

Execution control decisions are **source-specific strings**. Consumers must
**preserve the exact source decision string** and **must not** reinterpret or
normalise it through a different vocabulary. A `"partial"` from runtime X is not
the same as a `"partial"` from runtime Y unless both runtimes share a published
contract.

### Relationship to runtime_action

An execution_control decision may be informed by one or more runtime_action
decisions (e.g. a `BLOCK` on a critical tool may cause the execution controller
to emit `"stop"`), but the domains remain separate. Execution control operates at
the **run/loop level**; runtime_action operates at the **tool-call level**.

### Boundary

This domain is a **projection over source runtime metadata**. It does not define
a canonical execution control taxonomy. Consumers must accept whatever vocabulary
the source runtime publishes.

## Domain: post_run_audit

### Subject

The subject is a **completed evidence package**. After a run finishes, its
captured evidence (timeline, decisions, artefacts) is validated as a package to
produce a pass/warn/fail judgement about the evidence quality.

### Vocabulary

Uses the `AuditDecision` semantics defined in `src/ailuros/core/audit.py:8`:

| Value | Meaning | Condition |
|---|---|---|
| `pass` | Evidence is clean and contract-valid. | No errors and no warnings. |
| `warn` | Evidence is valid but has tolerated anomalies. | No errors, one or more warnings. |
| `fail` | Evidence violates the package contract. | One or more errors. |

`fail` always takes priority: if any error exists the decision is `fail`, even
when warnings are also present.

### Not Execution Outcome Reinterpretation

The post_run_audit judgement is strictly about **evidence quality**, not about
whether the original run "succeeded" or "failed". A run that produced blocking
decisions can still produce a `pass` audit if its evidence is well-formed. A run
that appeared to succeed can produce a `fail` audit if its evidence is incomplete
or malformed.

### Boundary

This domain is **after-the-fact validation only**. It has no runtime control
surface, no allow/block/review API, and no policy DSL. It is equivalent to a lint
result for an evidence package.

## Generic DecisionRecord Projection

Any decision from any domain can be projected into a source-neutral
`DecisionRecord` structure. This is a **read-side projection**, not a persistence
or write model.

### Fields

| Field | Type | Description |
|---|---|---|
| `domain` | `str` | Decision domain: `"runtime_action"`, `"execution_control"`, or `"post_run_audit"`. |
| `subject` | `str` | What the decision is about (tool name, run identifier, evidence package path). |
| `decision` | `str` | The domain-specific decision value as a string. |
| `reason` | `str` | Human-readable explanation. |
| `timestamp` | `str` | ISO-8601 timestamp with timezone when the decision was made. |
| `evidence_refs` | `list[str]` | Ordered references to evidence items that informed the decision. |
| `source` | `dict[str, Any]` | Source metadata: `run_id`, `source_type`, `source_version`, and any additional domain-specific fields. |

### Domain Mapping

| Domain | subject source | decision source | source.run_id |
|---|---|---|---|
| `runtime_action` | `GovernanceDecision.tool_name` | `GovernanceDecision.decision.value` | `GovernanceDecision.run_id` |
| `execution_control` | Source runtime run identifier | Source runtime decision string (preserved) | Source runtime run identifier |
| `post_run_audit` | Evidence package path or identifier | `AuditDecision.value` | `AuditResult.run_id` |

### Invariants

1. The `decision` field is always the **original string** from the source domain.
   It must not be transcoded into a different vocabulary.
2. The `domain` field is the discriminator. Consumers use it to select the
   correct interpretation of the `decision` field.
3. `evidence_refs` is never empty for `runtime_action` decisions produced by the
   policy engine. It may be empty for other domains.
4. The `source` metadata block is extensible but the keys `run_id`,
   `source_type`, and `source_version` are reserved.

## Explicit Non-Goals

- **No enum unification.** The three decision domains keep separate vocabularies.
  `DecisionRecord.decision` is always a `str`, never a unified enum.
- **No implementation in this pack.** This is a source-neutral contract document.
  Implementations live in the relevant runtime, adapter, or storage modules.
- **No canonical execution_control taxonomy.** The execution_control domain
  preserves source strings; it does not define a universal set of control verbs.

## Open Issues

- `planner_proposed_accept_and_no_blocking_rule_triggered` — reconcile execution
  control vocabulary with the Ailuros runtime's `ACCEPT` notion. When a planner
  proposes acceptance and no blocking rules fire, the execution_control
  projection should express that clearly without conflating it with a
  runtime_action `ALLOW`.
