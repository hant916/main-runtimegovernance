# Governance Decision Contract

**Status:** Adopted

**Date:** 2026-06-04

## Purpose

This contract defines the minimal decision semantics of the Ailuros governance
runtime. Every tool call that passes through the runtime produces exactly one
`GovernanceDecision`. That decision's `decision` and `allowed` fields together
determin whether tool execution proceeds, is blocked, or requires human review.

This contract is the bone structure of the runtime. All policy engines, decision
resolvers, adapters, and audit consumers depend on these semantics.

## Decision States

Ailuros defines five decision states via `GovernanceDecisionType`
(`src/ailuros/models/decision.py:10`):

| Enum Member | String Value | `allowed` | Execution Meaning |
|---|---|---|---|
| `ALLOW` | `"allow"` | `True` | Tool execution may proceed under the current runtime policy. |
| `WARN` | `"warn"` | `True` | Tool execution may proceed; a warning has been recorded. |
| `SANITIZE` | `"sanitize"` | `False` | Tool execution must not silently proceed; the result requires sanitisation before use. |
| `REQUIRE_REVIEW` | `"require_review"` | `False` | Tool execution must not silently proceed; human review is required first. |
| `BLOCK` | `"block"` | `False` | Tool execution must not proceed. The call is unconditionally rejected. |

Contracts from the machine core:

- **allow** means tool execution may proceed under the current runtime policy.
- **block** means tool execution must not proceed.
- **review/reject** means tool execution must not silently proceed (`allowed=False`).

The `allowed` field is the single boolean that gates tool execution in the
runtime (`src/ailuros/runtime/runtime.py:234`):

```python
if not decision.allowed:
    return ToolExecutionResult(blocked=True, decision=decision)
```

## Reason and Evidence

Every `GovernanceDecision` carries an explicit `reason` string and optional
`evidence_refs` list (`src/ailuros/models/decision.py:18`). These fields exist
to support audit, replay, and evaluation workflows. They are populated at
decision-creation time by the `DecisionResolver` or by policy match metadata.

- `reason`: human-readable explanation of why this decision was made.
- `evidence_refs`: list of event IDs or external reference identifiers that
  contributed to the decision.

## Decision Resolution

The `DecisionResolver` (`src/ailuros/policy/decision_resolver.py`) resolves
multiple matching policies into a single `GovernanceDecision` using a strict
priority order:

| Priority | Decision State |
|---|---|
| 0 (highest) | BLOCK |
| 1 | REQUIRE_REVIEW |
| 2 | SANITIZE |
| 3 | WARN |
| 4 (lowest) | ALLOW |

If no policies match, the resolver returns an `ALLOW` decision with reason
"No matching policy." (`src/ailuros/policy/decision_resolver.py:24-32`).

The `allowed` boolean is derived from the winning decision state:

```python
allowed = winner.decision in {GovernanceDecisionType.ALLOW, GovernanceDecisionType.WARN}
```

## Invariants

1. Ailuros remains a governance runtime, not an agent framework, UI platform, or
   generic workflow engine.
2. Phase 5 capabilities (multi-tenant server, REST API, dashboard, adapter
   ecosystem) remain explicitly deferred.
3. Warnings are non-blocking unless explicitly configured as hard gates.
4. Validation failure blocks `ACCEPT` but does not by itself require
   `HUMAN_REVIEW`.
5. Every terminal outcome writes a report.
6. A dirty working tree is not a failure.
7. Decision `reason` and `evidence_refs` fields remain explicit where the model
   supports them.

## Boundary

This contract describes the v0.1.0 baseline. Future phases may extend the
decision taxonomy or introduce new decision-time behaviour, but the semantics
defined here (`allowed=True` → proceed, `allowed=False` → do not silently
proceed) are the minimal contract that all consumers must respect.
