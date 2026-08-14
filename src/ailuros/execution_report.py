from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ailuros.core.execution import (
    ChangeSummary,
    EvidenceRef,
    ExecutionProjection,
    Lifecycle,
    Outcome,
    RoleSummary,
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
    validation: str
    scope: str
    why_stopped: str
    outcome_reasons: list[OutcomeReason] = Field(default_factory=list)
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


def build_run_report(
    projection: ExecutionProjection,
    signals: list[GovernanceSignal],
) -> RunReport:
    return RunReport(
        run_id=projection.run_id,
        lifecycle=projection.lifecycle.value,
        outcome=projection.outcome.value,
        native_outcome=derive_native_outcome(
            projection.lifecycle, projection.decisions
        ).value,
        validation=projection.validation.value,
        scope=projection.scope.value,
        why_stopped=_derive_why_stopped(projection, signals),
        outcome_reasons=_build_outcome_reasons(signals),
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
    lines.append(f"| Validation | {report.validation} |")
    lines.append(f"| Scope | {report.scope} |")
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
