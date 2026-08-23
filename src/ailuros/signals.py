from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from ailuros._compat import StrEnum
from ailuros.core.execution import (
    ApprovalRecord,
    ApprovalState,
    AuthorityRecord,
    AuthorityState,
    BudgetRecord,
    DecisionSummary,
    EvidenceRef,
    ExecutionProjection,
    Scope,
    Validation,
)
from ailuros.models.common import Severity


class SignalType(StrEnum):
    VALIDATION_FAILURE = "validation_failure"
    REPEATED_VALIDATION_FAILURE = "repeated_validation_failure"
    EVIDENCE_INCONSISTENCY = "evidence_inconsistency"
    SCOPE_VIOLATION = "scope_violation"
    FORBIDDEN_PATH_TOUCHED = "forbidden_path_touched"
    BACKEND_FALLBACK = "backend_fallback"
    BACKEND_UNAVAILABLE = "backend_unavailable"
    CONTEXT_TOO_LARGE = "context_too_large"
    CODER_SEMANTIC_FAILURE = "coder_semantic_failure"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    APPROVAL_REQUIRED_UNRESOLVED = "approval_required_unresolved"
    APPROVAL_DENIED = "approval_denied"
    BUDGET_EXCEEDED = "budget_exceeded"
    BUDGET_UNKNOWN = "budget_unknown"
    AUTHORITY_VIOLATION = "authority_violation"
    AUTHORITY_UNKNOWN = "authority_unknown"


RULE_VERSION = "1.0.0"


def _make_signal_id(
    run_id: str,
    signal_type: str,
    subject: str,
    evidence_refs: list[EvidenceRef],
    scope_ref: str | None = None,
) -> str:
    evidence_identity = ":".join(sorted(r.event_id for r in evidence_refs))
    if scope_ref is None:
        raw = f"{run_id}:{signal_type}:{subject}:{evidence_identity}"
    else:
        raw = f"{run_id}:{signal_type}:{subject}:{scope_ref}:{evidence_identity}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _decision_to_dict(d: DecisionSummary) -> dict[str, str]:
    return {
        "domain": d.domain,
        "decision": d.decision,
        "projected_domain": d.projected_domain,
    }


def _decision_matches(decision: DecisionSummary, patterns: set[str]) -> bool:
    return decision.decision in patterns


def _dedupe_evidence_refs(refs: list[EvidenceRef]) -> list[EvidenceRef]:
    """Return refs de-duplicated by event_id, preserving first-seen order."""
    seen: set[str] = set()
    deduped: list[EvidenceRef] = []
    for ref in refs:
        if ref.event_id in seen:
            continue
        seen.add(ref.event_id)
        deduped.append(ref)
    return deduped


def _decision_domain_matches(decision: DecisionSummary, domains: set[str]) -> bool:
    return decision.projected_domain in domains or decision.domain in domains


class GovernanceSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_id: str
    run_id: str
    type: str
    severity: str
    subject: str
    scope_ref: str | None = None
    details: dict[str, Any]
    evidence_refs: list[EvidenceRef]
    rule_version: str
    created_at: datetime

    @field_validator("scope_ref", mode="before")
    @classmethod
    def require_scope_ref_string(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        raise ValueError("scope_ref must be a string or None")

    @staticmethod
    def build(
        run_id: str,
        signal_type: SignalType,
        severity: Severity,
        subject: str,
        details: dict[str, Any],
        evidence_refs: list[EvidenceRef],
        scope_ref: str | None = None,
    ) -> GovernanceSignal:
        return GovernanceSignal(
            signal_id=_make_signal_id(
                run_id, signal_type.value, subject, evidence_refs, scope_ref
            ),
            run_id=run_id,
            type=signal_type.value,
            severity=severity.value,
            subject=subject,
            scope_ref=scope_ref,
            details=details,
            evidence_refs=evidence_refs,
            rule_version=RULE_VERSION,
            created_at=datetime.now(UTC),
        )


def _validation_failure_rule(projection: ExecutionProjection) -> list[GovernanceSignal]:
    if projection.validation != Validation.FAILED:
        return []
    return [
        GovernanceSignal.build(
            run_id=projection.run_id,
            signal_type=SignalType.VALIDATION_FAILURE,
            severity=Severity.HIGH,
            subject="validation",
            details={"validation": projection.validation.value},
            evidence_refs=list(projection.evidence_refs),
        )
    ]


def _repeated_validation_failure_rule(
    projection: ExecutionProjection,
) -> list[GovernanceSignal]:
    if projection.validation != Validation.FAILED:
        return []
    blocking_decisions = [
        d
        for d in projection.decisions
        if d.decision in {"block", "fail", "blocked"}
        and d.projected_domain != "post_run_audit"
    ]
    if len(blocking_decisions) < 2:
        return []
    return [
        GovernanceSignal.build(
            run_id=projection.run_id,
            signal_type=SignalType.REPEATED_VALIDATION_FAILURE,
            severity=Severity.HIGH,
            subject="repeated_validation",
            details={
                "validation": projection.validation.value,
                "failure_count": len(blocking_decisions),
                "triggering_decisions": [
                    _decision_to_dict(d) for d in blocking_decisions
                ],
            },
            evidence_refs=list(projection.evidence_refs),
        )
    ]


def _evidence_inconsistency_rule(
    projection: ExecutionProjection,
) -> list[GovernanceSignal]:
    domains: dict[tuple[str | None, str], set[str]] = {}
    for d in projection.decisions:
        key = (d.scope_ref, d.projected_domain)
        domains.setdefault(key, set()).add(d.decision)

    conflicts: list[dict[str, Any]] = []
    for (scope_ref, domain_key), decisions in domains.items():
        has_allow = "allow" in decisions
        has_deny = bool({"block", "fail", "blocked", "deny"} & decisions)
        if has_allow and has_deny:
            conflicts.append(
                {
                    "scope_ref": scope_ref,
                    "projected_domain": domain_key,
                    "decisions": sorted(decisions),
                }
            )

    if not conflicts:
        return []

    return [
        GovernanceSignal.build(
            run_id=projection.run_id,
            signal_type=SignalType.EVIDENCE_INCONSISTENCY,
            severity=Severity.MEDIUM,
            subject="evidence",
            details={"conflicts": conflicts},
            evidence_refs=list(projection.evidence_refs),
        )
    ]


def _scope_violation_rule(projection: ExecutionProjection) -> list[GovernanceSignal]:
    if projection.scope != Scope.VIOLATED:
        return []
    return [
        GovernanceSignal.build(
            run_id=projection.run_id,
            signal_type=SignalType.SCOPE_VIOLATION,
            severity=Severity.CRITICAL,
            subject="scope",
            details={"scope": projection.scope.value},
            evidence_refs=list(projection.evidence_refs),
        )
    ]


_FORBIDDEN_PATH_PATTERNS: set[str] = {
    "forbidden_path",
    "forbidden_path_touched",
    "path_violation",
    "scope_violation",
    "out_of_scope",
}


def _forbidden_path_touched_rule(
    projection: ExecutionProjection,
) -> list[GovernanceSignal]:
    path_decisions = [
        d
        for d in projection.decisions
        if d.decision in _FORBIDDEN_PATH_PATTERNS
        or d.domain in _FORBIDDEN_PATH_PATTERNS
        or d.projected_domain in _FORBIDDEN_PATH_PATTERNS
    ]
    if not path_decisions:
        return []
    return [
        GovernanceSignal.build(
            run_id=projection.run_id,
            signal_type=SignalType.FORBIDDEN_PATH_TOUCHED,
            severity=Severity.HIGH,
            subject="path",
            details={
                "paths": [_decision_to_dict(d) for d in path_decisions],
                "triggering_decisions": [
                    _decision_to_dict(d) for d in path_decisions
                ],
            },
            evidence_refs=list(projection.evidence_refs),
        )
    ]


_FALLBACK_PATTERNS: set[str] = {"fallback", "backend_fallback", "fell_back"}


def _backend_fallback_rule(projection: ExecutionProjection) -> list[GovernanceSignal]:
    fallback_decisions = [
        d
        for d in projection.decisions
        if d.decision in _FALLBACK_PATTERNS
        or d.domain in _FALLBACK_PATTERNS
    ]
    if not fallback_decisions:
        return []
    return [
        GovernanceSignal.build(
            run_id=projection.run_id,
            signal_type=SignalType.BACKEND_FALLBACK,
            severity=Severity.MEDIUM,
            subject="backend",
            details={
                "triggering_decisions": [
                    _decision_to_dict(d) for d in fallback_decisions
                ],
            },
            evidence_refs=list(projection.evidence_refs),
        )
    ]


_BACKEND_UNAVAILABLE_PATTERNS: set[str] = {
    "unavailable",
    "backend_unavailable",
    "service_unavailable",
}


def _backend_unavailable_rule(
    projection: ExecutionProjection,
) -> list[GovernanceSignal]:
    unavailable_decisions = [
        d
        for d in projection.decisions
        if d.decision in _BACKEND_UNAVAILABLE_PATTERNS
        or d.domain in _BACKEND_UNAVAILABLE_PATTERNS
    ]
    if not unavailable_decisions:
        return []
    return [
        GovernanceSignal.build(
            run_id=projection.run_id,
            signal_type=SignalType.BACKEND_UNAVAILABLE,
            severity=Severity.HIGH,
            subject="backend",
            details={
                "triggering_decisions": [
                    _decision_to_dict(d) for d in unavailable_decisions
                ],
            },
            evidence_refs=list(projection.evidence_refs),
        )
    ]


_CONTEXT_TOO_LARGE_PATTERNS: set[str] = {"context_too_large", "context_overflow", "token_limit"}


def _context_too_large_rule(projection: ExecutionProjection) -> list[GovernanceSignal]:
    context_decisions = [
        d
        for d in projection.decisions
        if d.decision in _CONTEXT_TOO_LARGE_PATTERNS
        or d.domain in _CONTEXT_TOO_LARGE_PATTERNS
    ]
    if not context_decisions:
        return []
    return [
        GovernanceSignal.build(
            run_id=projection.run_id,
            signal_type=SignalType.CONTEXT_TOO_LARGE,
            severity=Severity.LOW,
            subject="context",
            details={
                "triggering_decisions": [
                    _decision_to_dict(d) for d in context_decisions
                ],
            },
            evidence_refs=list(projection.evidence_refs),
        )
    ]


_CODER_SEMANTIC_FAILURE_PATTERNS: set[str] = {
    "semantic_failure",
    "coder_semantic_failure",
    "planner_semantic_failure",
    "code_generation_failure",
}


def _coder_semantic_failure_rule(
    projection: ExecutionProjection,
) -> list[GovernanceSignal]:
    coder_decisions = [
        d
        for d in projection.decisions
        if d.decision in _CODER_SEMANTIC_FAILURE_PATTERNS
    ]
    if not coder_decisions:
        return []
    return [
        GovernanceSignal.build(
            run_id=projection.run_id,
            signal_type=SignalType.CODER_SEMANTIC_FAILURE,
            severity=Severity.MEDIUM,
            subject="coder",
            details={
                "triggering_decisions": [
                    _decision_to_dict(d) for d in coder_decisions
                ],
            },
            evidence_refs=list(projection.evidence_refs),
        )
    ]


def _review_required_cause_evidence(
    projection: ExecutionProjection,
) -> list[EvidenceRef]:
    """Union of evidence refs from records that force a REVIEW_REQUIRED outcome.

    Mirrors _governed_outcome's review-required causes: unresolved-required
    approval records, unknown-required budget records, and unknown-required
    authority records. Returns [] when no record-backed cause exists (e.g. the
    outcome came from a require_review decision, which the projection cannot
    attribute to a specific event).
    """
    resolved_subject_actions = {
        _approval_subject_action(record)
        for record in projection.approval_records
        if record.state in {ApprovalState.APPROVED, ApprovalState.DENIED}
    }
    refs: list[EvidenceRef] = []
    for record in projection.approval_records:
        if (
            record.required is True
            and record.state == ApprovalState.UNKNOWN
            and _approval_subject_action(record) not in resolved_subject_actions
        ):
            refs.extend(record.evidence_refs)
    for record in projection.budget_records:
        if record.required is not True:
            continue
        status_lowered = record.status.strip().lower()
        values_are_sufficient = record.limit is not None and record.consumed is not None
        if not values_are_sufficient and status_lowered in _BUDGET_UNKNOWN_STATUSES:
            refs.extend(record.evidence_refs)
    for record in projection.authority_records:
        if record.required is True and record.state == AuthorityState.UNKNOWN:
            refs.extend(record.evidence_refs)
    return _dedupe_evidence_refs(refs)


def _human_review_required_rule(
    projection: ExecutionProjection,
) -> list[GovernanceSignal]:
    from ailuros.core.execution import Outcome

    if projection.outcome != Outcome.REVIEW_REQUIRED:
        return []
    cause_evidence = _review_required_cause_evidence(projection)
    evidence_refs = cause_evidence or list(projection.evidence_refs)
    return [
        GovernanceSignal.build(
            run_id=projection.run_id,
            signal_type=SignalType.HUMAN_REVIEW_REQUIRED,
            severity=Severity.MEDIUM,
            subject="review",
            details={"outcome": projection.outcome.value},
            evidence_refs=evidence_refs,
        )
    ]


def _approval_details(record: ApprovalRecord) -> dict[str, Any]:
    return {
        "subject": record.subject,
        "action": record.action,
        "approver_ref": record.approver_ref,
        "decision": record.decision,
        "state": record.state.value,
    }


def _approval_subject_action(record: ApprovalRecord) -> tuple[str, str | None]:
    return record.subject, record.action


def _approval_required_unresolved_rule(
    projection: ExecutionProjection,
) -> list[GovernanceSignal]:
    resolved_subject_actions = {
        _approval_subject_action(record)
        for record in projection.approval_records
        if record.state in {ApprovalState.APPROVED, ApprovalState.DENIED}
    }
    records = [
        r
        for r in projection.approval_records
        if (
            r.required is True
            and r.state == ApprovalState.UNKNOWN
            and _approval_subject_action(r) not in resolved_subject_actions
        )
    ]
    return [
        GovernanceSignal.build(
            run_id=projection.run_id,
            signal_type=SignalType.APPROVAL_REQUIRED_UNRESOLVED,
            severity=Severity.MEDIUM,
            subject="approval",
            details=_approval_details(r),
            evidence_refs=list(r.evidence_refs),
            scope_ref=r.scope_ref,
        )
        for r in records
    ]


def _approval_denied_rule(
    projection: ExecutionProjection,
) -> list[GovernanceSignal]:
    records = [
        r for r in projection.approval_records if r.state == ApprovalState.DENIED
    ]
    return [
        GovernanceSignal.build(
            run_id=projection.run_id,
            signal_type=SignalType.APPROVAL_DENIED,
            severity=Severity.HIGH,
            subject="approval",
            details=_approval_details(r),
            evidence_refs=list(r.evidence_refs),
            scope_ref=r.scope_ref,
        )
        for r in records
    ]


def _budget_details(record: BudgetRecord) -> dict[str, Any]:
    return {
        "subject": record.subject,
        "unit": record.unit,
        "scope_ref": record.scope_ref,
        "limit": record.limit,
        "consumed": record.consumed,
        "remaining": record.remaining,
        "status": record.status,
    }


_BUDGET_EXCEEDED_STATUSES: frozenset[str] = frozenset(
    {"exceeded", "exceed", "over_limit", "overlimit", "exhausted", "breached"}
)


def _budget_exceeded_rule(
    projection: ExecutionProjection,
) -> list[GovernanceSignal]:
    signals: list[GovernanceSignal] = []
    for record in projection.budget_records:
        status_lowered = record.status.strip().lower()
        explicit_exceeded = status_lowered in _BUDGET_EXCEEDED_STATUSES
        deterministic_exceeded = (
            record.limit is not None
            and record.consumed is not None
            and record.consumed > record.limit
        )
        if not explicit_exceeded and not deterministic_exceeded:
            continue
        signals.append(
            GovernanceSignal.build(
                run_id=projection.run_id,
                signal_type=SignalType.BUDGET_EXCEEDED,
                severity=Severity.HIGH,
                subject="budget",
                details=_budget_details(record),
                evidence_refs=list(record.evidence_refs),
                scope_ref=record.scope_ref,
            )
        )
    return signals


_BUDGET_UNKNOWN_STATUSES: frozenset[str] = frozenset({"", "unknown"})


def _budget_unknown_rule(
    projection: ExecutionProjection,
) -> list[GovernanceSignal]:
    signals: list[GovernanceSignal] = []
    for record in projection.budget_records:
        if record.required is not True:
            continue
        status_lowered = record.status.strip().lower()
        values_are_sufficient = record.limit is not None and record.consumed is not None
        insufficient = not values_are_sufficient and status_lowered in _BUDGET_UNKNOWN_STATUSES
        if not insufficient:
            continue
        signals.append(
            GovernanceSignal.build(
                run_id=projection.run_id,
                signal_type=SignalType.BUDGET_UNKNOWN,
                severity=Severity.MEDIUM,
                subject="budget",
                details=_budget_details(record),
                evidence_refs=list(record.evidence_refs),
                scope_ref=record.scope_ref,
            )
        )
    return signals


def _authority_details(record: AuthorityRecord) -> dict[str, Any]:
    return {
        "actor": record.actor,
        "action": record.action,
        "observed_target": record.observed_target,
        "requested_target": record.requested_target,
        "authority_source": record.authority_source,
        "state": record.state.value,
    }


def _authority_violation_rule(
    projection: ExecutionProjection,
) -> list[GovernanceSignal]:
    records = [
        r for r in projection.authority_records if r.state == AuthorityState.VIOLATION
    ]
    return [
        GovernanceSignal.build(
            run_id=projection.run_id,
            signal_type=SignalType.AUTHORITY_VIOLATION,
            severity=Severity.CRITICAL,
            subject="authority",
            details=_authority_details(r),
            evidence_refs=list(r.evidence_refs),
            scope_ref=r.scope_ref,
        )
        for r in records
    ]


def _authority_unknown_rule(
    projection: ExecutionProjection,
) -> list[GovernanceSignal]:
    records = [
        r
        for r in projection.authority_records
        if r.required is True and r.state == AuthorityState.UNKNOWN
    ]
    return [
        GovernanceSignal.build(
            run_id=projection.run_id,
            signal_type=SignalType.AUTHORITY_UNKNOWN,
            severity=Severity.MEDIUM,
            subject="authority",
            details=_authority_details(r),
            evidence_refs=list(r.evidence_refs),
            scope_ref=r.scope_ref,
        )
        for r in records
    ]


_RULES: list[Callable[[ExecutionProjection], list[GovernanceSignal]]] = [
    _validation_failure_rule,
    _repeated_validation_failure_rule,
    _evidence_inconsistency_rule,
    _scope_violation_rule,
    _forbidden_path_touched_rule,
    _backend_fallback_rule,
    _backend_unavailable_rule,
    _context_too_large_rule,
    _coder_semantic_failure_rule,
    _human_review_required_rule,
    _approval_required_unresolved_rule,
    _approval_denied_rule,
    _budget_exceeded_rule,
    _budget_unknown_rule,
    _authority_violation_rule,
    _authority_unknown_rule,
]


def derive_signals(projection: ExecutionProjection) -> list[GovernanceSignal]:
    signals: list[GovernanceSignal] = []
    for rule in _RULES:
        signals.extend(rule(projection))
    return signals
