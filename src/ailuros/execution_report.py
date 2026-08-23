from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ailuros.core.execution import (
    ChangeSummary,
    EvidenceRef,
    ExecutionProjection,
    GovernanceCoverage,
    GovernedOutcome,
    Lifecycle,
    Outcome,
    RoleSummary,
    ScopeOutcome,
    Validation,
)
from ailuros.projection import derive_native_outcome
from ailuros.signals import SignalType

if TYPE_CHECKING:
    from ailuros.signals import GovernanceSignal


class RunReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    lifecycle: str
    outcome: str
    native_outcome: str = ""
    governed_outcome: str = ""
    aggregate_governed_outcome: str = ""
    validation: str
    scope: str
    governance_coverage: GovernanceCoverage = Field(default_factory=GovernanceCoverage)
    scope_outcomes: list[ScopeOutcome] = Field(default_factory=list)
    why_stopped: str
    outcome_reasons: list[OutcomeReason] = Field(default_factory=list)
    governed_outcome_reasons: list[OutcomeReason] = Field(default_factory=list)
    signal_summaries: list[SignalSummary] = Field(default_factory=list)
    decision_reasons: list[str] = Field(default_factory=list)
    changes: list[ChangeSummary] = Field(default_factory=list)
    roles: list[RoleSummary] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    step_count: int = 0
    decision_count: int = 0
    event_count: int = 0
    started_at: datetime
    completed_at: datetime | None = None

    @field_validator("started_at", "completed_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class SignalSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_id: str
    type: str
    severity: str
    subject: str
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class OutcomeReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


def _derive_why_stopped(
    projection: ExecutionProjection,
    signals: list[GovernanceSignal],
) -> str:
    terminal_control = [
        d
        for d in projection.decisions
        if d.projected_domain == "execution_control"
    ]

    if terminal_control:
        decisions_str = ", ".join(f"{d.decision}" for d in terminal_control)
        return f"execution_control: {decisions_str}"

    if projection.outcome == Outcome.REVIEW_REQUIRED:
        return "outcome: review_required"
    if projection.outcome == Outcome.BLOCKED:
        return "outcome: blocked"

    signal_types = list({s.type for s in signals})
    if projection.lifecycle == Lifecycle.COMPLETED:
        suffix = f" (signals: {', '.join(signal_types)})" if signal_types else ""
        return f"lifecycle: {projection.lifecycle.value}{suffix}"
    if projection.lifecycle == Lifecycle.FAILED:
        suffix = f" (signals: {', '.join(signal_types)})" if signal_types else ""
        return f"lifecycle: {projection.lifecycle.value}{suffix}"

    if signal_types:
        return f"signals: {', '.join(sorted(signal_types))}"
    return "unknown"


def _build_decision_reasons(projection: ExecutionProjection) -> list[str]:
    reasons: list[str] = []
    for d in projection.decisions:
        reason = f"{d.projected_domain}/{d.decision}"
        if reason not in reasons:
            reasons.append(reason)
    return reasons


_APPROVAL_BUDGET_REASON_TYPES: frozenset[str] = frozenset(
    {
        SignalType.APPROVAL_DENIED.value,
        SignalType.APPROVAL_REQUIRED_UNRESOLVED.value,
        SignalType.BUDGET_EXCEEDED.value,
        SignalType.BUDGET_UNKNOWN.value,
    }
)


def _build_outcome_reasons(signals: list[GovernanceSignal]) -> list[OutcomeReason]:
    reasons: list[OutcomeReason] = []
    for signal in signals:
        if signal.type in _APPROVAL_BUDGET_REASON_TYPES:
            reasons.append(
                OutcomeReason(
                    code=signal.type,
                    evidence_refs=list(signal.evidence_refs),
                )
            )
    return reasons


_FAILED_SIGNAL_TYPES: frozenset[str] = frozenset(
    {
        SignalType.AUTHORITY_VIOLATION.value,
        SignalType.APPROVAL_DENIED.value,
        SignalType.BUDGET_EXCEEDED.value,
        SignalType.SCOPE_VIOLATION.value,
    }
)

_REVIEW_REQUIRED_SIGNAL_TYPES: frozenset[str] = frozenset(
    {
        SignalType.HUMAN_REVIEW_REQUIRED.value,
        SignalType.APPROVAL_REQUIRED_UNRESOLVED.value,
        SignalType.BUDGET_UNKNOWN.value,
        SignalType.AUTHORITY_UNKNOWN.value,
    }
)

_DEGRADED_SIGNAL_TYPES: frozenset[str] = frozenset(
    {
        SignalType.BACKEND_FALLBACK.value,
        SignalType.BACKEND_UNAVAILABLE.value,
        SignalType.CONTEXT_TOO_LARGE.value,
        SignalType.CODER_SEMANTIC_FAILURE.value,
        SignalType.EVIDENCE_INCONSISTENCY.value,
        SignalType.FORBIDDEN_PATH_TOUCHED.value,
        SignalType.REPEATED_VALIDATION_FAILURE.value,
    }
)


def _signals_by_type(
    signals: list[GovernanceSignal], types: frozenset[str]
) -> list[GovernanceSignal]:
    return [s for s in signals if s.type in types]


def _is_blocking_failure_signal(signal: GovernanceSignal) -> bool:
    if signal.type not in _FAILED_SIGNAL_TYPES:
        return False
    if signal.type != SignalType.APPROVAL_DENIED.value:
        return True
    return isinstance(signal.details.get("action"), str) and bool(
        signal.details["action"]
    )


def _classify_governed_outcome(
    outcome: Outcome,
    validation: Validation,
    lifecycle: Lifecycle,
    signals: list[GovernanceSignal],
) -> GovernedOutcome:
    failed_signals = [
        signal for signal in signals if _is_blocking_failure_signal(signal)
    ]
    if (
        outcome in {Outcome.FAILED, Outcome.BLOCKED}
        or validation == Validation.FAILED
        or failed_signals
    ):
        return GovernedOutcome.FAILED

    review_signals = _signals_by_type(signals, _REVIEW_REQUIRED_SIGNAL_TYPES)
    if outcome == Outcome.REVIEW_REQUIRED or review_signals:
        return GovernedOutcome.REVIEW_REQUIRED

    if (
        lifecycle not in {Lifecycle.COMPLETED, Lifecycle.FAILED}
        or outcome == Outcome.UNKNOWN
    ):
        return GovernedOutcome.UNKNOWN

    degraded_signals = _signals_by_type(signals, _DEGRADED_SIGNAL_TYPES)
    validation_degraded = validation in {
        Validation.PARTIAL,
        Validation.NOT_RUN,
        Validation.UNKNOWN,
    }
    if degraded_signals or validation_degraded:
        return GovernedOutcome.DEGRADED_SUCCESS

    if outcome == Outcome.SUCCESS and validation == Validation.PASSED:
        return GovernedOutcome.CLEAN_SUCCESS

    return GovernedOutcome.UNKNOWN


def _governed_outcome_reasons(
    governed: GovernedOutcome,
    projection: ExecutionProjection,
    signals: list[GovernanceSignal],
) -> list[OutcomeReason]:
    if governed == GovernedOutcome.FAILED:
        failed_signals = [
            signal for signal in signals if _is_blocking_failure_signal(signal)
        ]
        reasons = [
            OutcomeReason(code=s.type, evidence_refs=list(s.evidence_refs))
            for s in failed_signals
        ]
        if not reasons:
            reasons = [OutcomeReason(code=f"outcome/{projection.outcome.value}")]
        return reasons

    if governed == GovernedOutcome.REVIEW_REQUIRED:
        review_signals = _signals_by_type(signals, _REVIEW_REQUIRED_SIGNAL_TYPES)
        reasons = [
            OutcomeReason(code=s.type, evidence_refs=list(s.evidence_refs))
            for s in review_signals
        ]
        if not reasons:
            reasons = [OutcomeReason(code="outcome/review_required")]
        return reasons

    if governed == GovernedOutcome.UNKNOWN:
        if projection.lifecycle not in {Lifecycle.COMPLETED, Lifecycle.FAILED}:
            return [OutcomeReason(code=f"lifecycle/{projection.lifecycle.value}")]
        if projection.outcome == Outcome.UNKNOWN:
            return [OutcomeReason(code=f"lifecycle/{projection.lifecycle.value}")]
        return [OutcomeReason(code=f"outcome/{projection.outcome.value}")]

    if governed == GovernedOutcome.DEGRADED_SUCCESS:
        degraded_signals = _signals_by_type(signals, _DEGRADED_SIGNAL_TYPES)
        reasons = [
            OutcomeReason(code=s.type, evidence_refs=list(s.evidence_refs))
            for s in degraded_signals
        ]
        if not reasons:
            reasons = [OutcomeReason(code=f"validation/{projection.validation.value}")]
        return reasons

    return []


def derive_governed_outcome(
    projection: ExecutionProjection,
    signals: list[GovernanceSignal],
) -> tuple[GovernedOutcome, list[OutcomeReason]]:
    governed = _classify_governed_outcome(
        projection.outcome,
        projection.validation,
        projection.lifecycle,
        signals,
    )
    return governed, _governed_outcome_reasons(governed, projection, signals)


_GOVERNED_OUTCOME_PRECEDENCE: dict[GovernedOutcome, int] = {
    GovernedOutcome.FAILED: 4,
    GovernedOutcome.REVIEW_REQUIRED: 3,
    GovernedOutcome.UNKNOWN: 2,
    GovernedOutcome.DEGRADED_SUCCESS: 1,
    GovernedOutcome.CLEAN_SUCCESS: 0,
}


def aggregate_governed_outcomes(
    scoped_outcomes: list[ScopeOutcome],
) -> GovernedOutcome:
    """Aggregate per-scope governed outcomes deterministically.

    Precedence is conservative: any FAILED scope dominates, then
    REVIEW_REQUIRED, then UNKNOWN. An UNKNOWN scope therefore prevents any
    clean or degraded success claim (incomplete coverage is never inferred
    as clean). An empty list aggregates to UNKNOWN.
    """
    if not scoped_outcomes:
        return GovernedOutcome.UNKNOWN
    return max(
        (entry.outcome for entry in scoped_outcomes),
        key=lambda outcome: _GOVERNED_OUTCOME_PRECEDENCE[outcome],
    )


def derive_scope_outcomes(
    projection: ExecutionProjection,
    signals: list[GovernanceSignal],
) -> list[ScopeOutcome]:
    """Derive one governed outcome per scope from scope-attributed signals.

    Scopes are taken from the canonical scope-aware governance fact
    ``GovernanceSignal.scope_ref``. A scope that carried no signals is not
    represented and therefore can never contribute clean success. Run-level
    projection facts bound every scope so run-level failures are never
    masked by an otherwise clean scope.
    """
    by_scope: dict[str | None, list[GovernanceSignal]] = {}
    for signal in signals:
        by_scope.setdefault(signal.scope_ref, []).append(signal)

    results: list[ScopeOutcome] = []
    for scope_ref in sorted(by_scope, key=lambda ref: (ref is None, ref or "")):
        scoped_signals = by_scope[scope_ref]
        results.append(
            ScopeOutcome(
                scope_ref=scope_ref,
                outcome=_classify_governed_outcome(
                    projection.outcome,
                    projection.validation,
                    projection.lifecycle,
                    scoped_signals,
                ),
            )
        )
    return results


def build_run_report(
    projection: ExecutionProjection,
    signals: list[GovernanceSignal],
) -> RunReport:
    governed_outcome, governed_outcome_reasons = derive_governed_outcome(
        projection, signals
    )
    scope_outcomes = derive_scope_outcomes(projection, signals)
    aggregate_governed_outcome = (
        aggregate_governed_outcomes(scope_outcomes)
        if scope_outcomes
        else governed_outcome
    )
    return RunReport(
        run_id=projection.run_id,
        lifecycle=projection.lifecycle.value,
        outcome=projection.outcome.value,
        native_outcome=derive_native_outcome(
            projection.lifecycle, projection.decisions
        ).value,
        governed_outcome=governed_outcome.value,
        aggregate_governed_outcome=aggregate_governed_outcome.value,
        validation=projection.validation.value,
        scope=projection.scope.value,
        governance_coverage=projection.governance_coverage,
        scope_outcomes=scope_outcomes,
        why_stopped=_derive_why_stopped(projection, signals),
        outcome_reasons=_build_outcome_reasons(signals),
        governed_outcome_reasons=governed_outcome_reasons,
        signal_summaries=[
            SignalSummary(
                signal_id=s.signal_id,
                type=s.type,
                severity=s.severity,
                subject=s.subject,
                evidence_refs=list(s.evidence_refs),
            )
            for s in signals
        ],
        decision_reasons=_build_decision_reasons(projection),
        changes=list(projection.changes),
        roles=list(projection.roles),
        evidence_refs=list(projection.evidence_refs),
        step_count=projection.step_count,
        decision_count=projection.decision_count,
        event_count=projection.event_count,
        started_at=projection.started_at,
        completed_at=projection.completed_at,
    )


def render_run_report_json(report: RunReport) -> str:
    return report.model_dump_json(indent=2)


def render_run_report_markdown(
    report: RunReport,
    *,
    title: str = "Run Report",
) -> str:
    lines: list[str] = []

    lines.append(f"# {title}")
    lines.append("")

    lines.append("## Headline")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append(f"| Run ID | {report.run_id} |")
    lines.append(f"| Lifecycle | {report.lifecycle} |")
    lines.append(f"| Outcome | {report.outcome} |")
    lines.append(f"| Native Outcome | {report.native_outcome} |")
    lines.append(f"| Governed Outcome | {report.governed_outcome} |")
    lines.append(f"| Aggregate Governed Outcome | {report.aggregate_governed_outcome} |")
    lines.append(f"| Validation | {report.validation} |")
    lines.append(f"| Scope | {report.scope} |")
    lines.append("")

    lines.append("## Governance Coverage")
    lines.append("")
    lines.append("| Dimension | Coverage |")
    lines.append("|---|---|")
    for dimension in ("authority", "approval", "budget", "validation", "scope"):
        lines.append(
            f"| {dimension} | {getattr(report.governance_coverage, dimension).value} |"
        )
    lines.append("")

    lines.append("## Scope Outcomes")
    lines.append("")
    if report.scope_outcomes:
        lines.append("| Scope | Governed Outcome |")
        lines.append("|---|---|")
        for scope_outcome in report.scope_outcomes:
            scope_label = scope_outcome.scope_ref or "unscoped"
            lines.append(f"| {scope_label} | {scope_outcome.outcome.value} |")
    else:
        lines.append("None.")
    lines.append("")

    lines.append("## Why Stopped")
    lines.append("")
    lines.append(report.why_stopped)
    lines.append("")

    lines.append("## Outcome Reasons")
    lines.append("")
    if report.outcome_reasons:
        for outcome_reason in report.outcome_reasons:
            ref_ids = ", ".join(r.event_id for r in outcome_reason.evidence_refs) or "none"
            lines.append(f"- `{outcome_reason.code}` ({ref_ids})")
    else:
        lines.append("None.")
    lines.append("")

    lines.append("## Governed Outcome Reasons")
    lines.append("")
    if report.governed_outcome_reasons:
        for outcome_reason in report.governed_outcome_reasons:
            ref_ids = ", ".join(r.event_id for r in outcome_reason.evidence_refs) or "none"
            lines.append(f"- `{outcome_reason.code}` ({ref_ids})")
    else:
        lines.append("None.")
    lines.append("")

    lines.append("## Timeline")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append(f"| Steps | {report.step_count} |")
    lines.append(f"| Decisions | {report.decision_count} |")
    lines.append(f"| Events | {report.event_count} |")
    lines.append(f"| Started | {report.started_at.isoformat()} |")
    if report.completed_at is not None:
        lines.append(f"| Completed | {report.completed_at.isoformat()} |")
    lines.append("")

    lines.append("## Decision Reasons")
    lines.append("")
    if report.decision_reasons:
        for decision_reason in report.decision_reasons:
            lines.append(f"- `{decision_reason}`")
    else:
        lines.append("None.")
    lines.append("")

    lines.append("## Signals")
    lines.append("")
    if report.signal_summaries:
        lines.append("| ID | Type | Severity | Subject | Refs |")
        lines.append("|---|---|---|---|---|")
        for s in report.signal_summaries:
            ref_ids = ", ".join(r.event_id for r in s.evidence_refs) or "none"
            lines.append(f"| {s.signal_id} | {s.type} | {s.severity} | {s.subject} | {ref_ids} |")
    else:
        lines.append("None.")
    lines.append("")

    lines.append("## Changes")
    lines.append("")
    if report.changes:
        for change in report.changes:
            lines.append(f"- {change.description}")
    else:
        lines.append("None.")
    lines.append("")

    lines.append("## Roles")
    lines.append("")
    if report.roles:
        for role in report.roles:
            lines.append(f"- {role.name}")
    else:
        lines.append("None.")
    lines.append("")

    lines.append("## Evidence Index")
    lines.append("")
    if report.evidence_refs:
        for ref in report.evidence_refs:
            parts: list[str] = [ref.event_id]
            if ref.artifact:
                parts.append(f"artifact: {ref.artifact}")
            if ref.pointer:
                parts.append(f"pointer: {ref.pointer}")
            lines.append(f"- {', '.join(parts)}")
    else:
        lines.append("None.")
    lines.append("")

    return "\n".join(lines)
