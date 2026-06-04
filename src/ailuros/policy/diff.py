from dataclasses import dataclass, field
from typing import Any

from ailuros.models import GovernanceDecision, GovernanceDecisionType, Severity

_DECISION_SEVERITY: dict[GovernanceDecisionType, int] = {
    GovernanceDecisionType.ALLOW: 0,
    GovernanceDecisionType.WARN: 1,
    GovernanceDecisionType.SANITIZE: 2,
    GovernanceDecisionType.REQUIRE_REVIEW: 3,
    GovernanceDecisionType.BLOCK: 4,
}

_SEVERITY_RANK: dict[Severity, int] = {
    Severity.LOW: 0,
    Severity.MEDIUM: 1,
    Severity.HIGH: 2,
    Severity.CRITICAL: 3,
}


@dataclass(frozen=True)
class FieldDiff:
    field: str
    kind: str
    old_value: Any
    new_value: Any
    message: str


@dataclass(frozen=True)
class PolicyDecisionDiff:
    old_decision_id: str
    new_decision_id: str
    diffs: list[FieldDiff] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return any(d.kind != "unchanged" for d in self.diffs)

    @property
    def change_summary(self) -> str:
        changes = [d for d in self.diffs if d.kind != "unchanged"]
        if not changes:
            return "No changes detected."
        return "; ".join(d.message for d in changes)


def diff_decisions(
    old: GovernanceDecision, new: GovernanceDecision
) -> PolicyDecisionDiff:
    diffs: list[FieldDiff] = []

    _diff_decision_field(diffs, old, new)
    _diff_severity_field(diffs, old, new)
    _diff_allowed_field(diffs, old, new)
    _diff_reason_field(diffs, old, new)
    _diff_matched_policy_ids_field(diffs, old, new)

    diffs.sort(key=lambda d: _field_sort_key(d.field))

    return PolicyDecisionDiff(
        old_decision_id=old.decision_id,
        new_decision_id=new.decision_id,
        diffs=diffs,
    )


_FIELD_ORDER = {
    "decision": 0,
    "severity": 1,
    "allowed": 2,
    "reason": 3,
    "matched_policy_ids": 4,
}


def _field_sort_key(field: str) -> int:
    return _FIELD_ORDER.get(field, 99)


def _diff_decision_field(
    diffs: list[FieldDiff],
    old: GovernanceDecision,
    new: GovernanceDecision,
) -> None:
    if old.decision == new.decision:
        diffs.append(FieldDiff(
            field="decision",
            kind="unchanged",
            old_value=old.decision.value,
            new_value=new.decision.value,
            message=f"Decision unchanged ({old.decision.value}).",
        ))
        return

    old_rank = _DECISION_SEVERITY[old.decision]
    new_rank = _DECISION_SEVERITY[new.decision]

    if new_rank > old_rank:
        kind = "upgrade"
    elif new_rank < old_rank:
        kind = "downgrade"
    else:
        kind = "changed"

    diffs.append(FieldDiff(
        field="decision",
        kind=kind,
        old_value=old.decision.value,
        new_value=new.decision.value,
        message=f"Decision {kind}: {old.decision.value} -> {new.decision.value}",
    ))


def _diff_severity_field(
    diffs: list[FieldDiff],
    old: GovernanceDecision,
    new: GovernanceDecision,
) -> None:
    if old.severity == new.severity:
        diffs.append(FieldDiff(
            field="severity",
            kind="unchanged",
            old_value=old.severity.value,
            new_value=new.severity.value,
            message=f"Severity unchanged ({old.severity.value}).",
        ))
        return

    old_rank = _SEVERITY_RANK[old.severity]
    new_rank = _SEVERITY_RANK[new.severity]

    if new_rank > old_rank:
        kind = "upgrade"
    elif new_rank < old_rank:
        kind = "downgrade"
    else:
        kind = "changed"

    diffs.append(FieldDiff(
        field="severity",
        kind=kind,
        old_value=old.severity.value,
        new_value=new.severity.value,
        message=f"Severity {kind}: {old.severity.value} -> {new.severity.value}",
    ))


def _diff_allowed_field(
    diffs: list[FieldDiff],
    old: GovernanceDecision,
    new: GovernanceDecision,
) -> None:
    if old.allowed == new.allowed:
        diffs.append(FieldDiff(
            field="allowed",
            kind="unchanged",
            old_value=old.allowed,
            new_value=new.allowed,
            message=f"Allowed unchanged ({old.allowed}).",
        ))
        return

    kind = "downgrade" if old.allowed and not new.allowed else "upgrade"

    diffs.append(FieldDiff(
        field="allowed",
        kind=kind,
        old_value=old.allowed,
        new_value=new.allowed,
        message=f"Allowed {kind}: {old.allowed} -> {new.allowed}",
    ))


def _diff_reason_field(
    diffs: list[FieldDiff],
    old: GovernanceDecision,
    new: GovernanceDecision,
) -> None:
    if old.reason == new.reason:
        diffs.append(FieldDiff(
            field="reason",
            kind="unchanged",
            old_value=old.reason,
            new_value=new.reason,
            message="Reason unchanged.",
        ))
        return

    diffs.append(FieldDiff(
        field="reason",
        kind="changed",
        old_value=old.reason,
        new_value=new.reason,
        message="Reason changed.",
    ))


def _diff_matched_policy_ids_field(
    diffs: list[FieldDiff],
    old: GovernanceDecision,
    new: GovernanceDecision,
) -> None:
    old_ids = sorted(old.matched_policy_ids)
    new_ids = sorted(new.matched_policy_ids)

    if old_ids == new_ids:
        diffs.append(FieldDiff(
            field="matched_policy_ids",
            kind="unchanged",
            old_value=old_ids,
            new_value=new_ids,
            message="Matched policy IDs unchanged.",
        ))
        return

    added = sorted(set(new_ids) - set(old_ids))
    removed = sorted(set(old_ids) - set(new_ids))

    parts = []
    if added:
        parts.append(f"added: [{', '.join(added)}]")
    if removed:
        parts.append(f"removed: [{', '.join(removed)}]")

    diffs.append(FieldDiff(
        field="matched_policy_ids",
        kind="changed",
        old_value=old_ids,
        new_value=new_ids,
        message=f"Matched policy IDs changed ({'; '.join(parts)}).",
    ))
