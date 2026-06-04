# Policy Decision Diff

## Overview

`PolicyDecisionDiff` compares two `GovernanceDecision` objects and produces a deterministic, explainable diff for governance review. It is a reporting/explainability feature, not an enforcement mechanism.

## API

### `diff_decisions(old, new) -> PolicyDecisionDiff`

Compares two `GovernanceDecision` instances field-by-field.

**Parameters:**
- `old: GovernanceDecision` - previous decision
- `new: GovernanceDecision` - current decision

**Returns:** `PolicyDecisionDiff` with:
- `old_decision_id: str`
- `new_decision_id: str`
- `diffs: list[FieldDiff]` - ordered list of field-level differences
- `has_changes: bool` - whether any diff is not "unchanged"
- `change_summary: str` - semicolon-separated human-readable summary of changes

### `FieldDiff`

| Field | Type | Description |
|-------|------|-------------|
| `field` | `str` | Field name (decision, severity, allowed, reason, matched_policy_ids) |
| `kind` | `str` | upgrade, downgrade, changed, or unchanged |
| `old_value` | `Any` | Previous value |
| `new_value` | `Any` | Current value |
| `message` | `str` | Human-readable description |

## Compared Fields

| Field | Order | Kinds |
|-------|-------|-------|
| `decision` | 0 | upgrade, downgrade, changed, unchanged |
| `severity` | 1 | upgrade, downgrade, changed, unchanged |
| `allowed` | 2 | upgrade, downgrade, unchanged |
| `reason` | 3 | changed, unchanged |
| `matched_policy_ids` | 4 | changed, unchanged |

## Upgrade/Downgrade Semantics

- **Decision**: ALLOW (least restrictive) < WARN < SANITIZE < REQUIRE_REVIEW < BLOCK (most restrictive)
- **Severity**: LOW < MEDIUM < HIGH < CRITICAL
- **Allowed**: True -> False = downgrade; False -> True = upgrade

## Determinism

- Diff output order is fixed by `_FIELD_ORDER`
- Matched policy IDs are sorted before comparison
- Repeated calls with same inputs produce identical results

## Scope and Red Lines

- This diff is **reporting/explainability only** - it does not gate or block any decision
- Policy resolution priority is not changed
- No new enforcement paths are introduced
- Governance strictness defaults are not altered
