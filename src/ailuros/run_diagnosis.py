from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from ailuros._compat import StrEnum
from ailuros.core.execution import (
    EvidenceRef,
    ExecutionProjection,
    Lifecycle,
    Outcome,
    Scope,
    Validation,
)
from ailuros.signals import SignalType

if TYPE_CHECKING:
    from ailuros.signals import GovernanceSignal


class IncompleteWork(StrEnum):
    NONE = "none"
    RUN_FAILED = "run_failed"
    RUN_INTERRUPTED = "run_interrupted"
    ACCEPTANCE_UNPROVEN = "acceptance_unproven"
    BLOCKED_OR_REVIEW = "blocked_or_review"


class RootCause(StrEnum):
    EXECUTION_RUNTIME_PROCESS_SUPERVISION = "execution_runtime/process_supervision"
    SCOPE_BOUNDARY = "scope_boundary"
    VALIDATION = "validation"
    UNPROVEN_COMPLETION = "unproven_completion"
    PACK_DEFINITION = "pack_definition"
    EVIDENCE_INCONSISTENT = "evidence_inconsistent"
    UNKNOWN = "unknown"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class NextAction(StrEnum):
    NONE = "none"
    RETRY = "retry"
    REPAIR_RUNTIME = "repair_runtime"
    REPAIR_PACK_DEFINITION = "repair_pack_definition"
    CONFIRM_RECONCILE = "confirm_reconcile"
    STOP = "stop"
    HUMAN_REVIEW = "human_review"
    INSPECT = "inspect"


class RunDiagnosis(BaseModel):
    """Deterministic, advisory operator diagnosis over canonical run evidence.

    The four bounded fields answer the operator questions: what did not
    complete (`incomplete`), what evidence-backed root-cause class is visible
    (`root_cause`), what is the current risk (`risk`), and what should happen
    next (`next_action`). Only canonical structured facts are used; nothing is
    inferred from raw logs and no producer-specific branch is applied.
    """

    model_config = ConfigDict(extra="forbid")

    run_id: str
    incomplete: IncompleteWork
    root_cause: RootCause
    root_cause_detail: str = "unknown"
    risk: RiskLevel
    next_action: NextAction
    next_action_note: str = ""
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


_SCOPE_SIGNAL_TYPES: frozenset[str] = frozenset(
    {SignalType.SCOPE_VIOLATION.value, SignalType.FORBIDDEN_PATH_TOUCHED.value}
)

_VALIDATION_FAILURE_SIGNAL_TYPES: frozenset[str] = frozenset(
    {
        SignalType.VALIDATION_FAILURE.value,
        SignalType.REPEATED_VALIDATION_FAILURE.value,
    }
)

_EVIDENCE_INCONSISTENCY_SIGNAL_TYPES: frozenset[str] = frozenset(
    {SignalType.EVIDENCE_INCONSISTENCY.value}
)

_GOVERNED_STOP_SIGNAL_TYPES: frozenset[str] = frozenset(
    {
        SignalType.AUTHORITY_VIOLATION.value,
        SignalType.APPROVAL_DENIED.value,
        SignalType.BUDGET_EXCEEDED.value,
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

_EXPLICIT_SUB_CAUSE_SIGNAL_TYPES: frozenset[str] = frozenset(
    {
        SignalType.BACKEND_UNAVAILABLE.value,
        SignalType.CONTEXT_TOO_LARGE.value,
        SignalType.CODER_SEMANTIC_FAILURE.value,
        SignalType.BACKEND_FALLBACK.value,
    }
)


def _signals_of_type(
    signals: list[GovernanceSignal], types: frozenset[str]
) -> list[GovernanceSignal]:
    return [signal for signal in signals if signal.type in types]


def _collect_evidence_refs(
    projection: ExecutionProjection,
    signals: list[GovernanceSignal],
) -> list[EvidenceRef]:
    refs: list[EvidenceRef] = []
    seen: set[str] = set()
    for ref in list(projection.evidence_refs) + [
        ref for signal in signals for ref in signal.evidence_refs
    ]:
        if ref.event_id in seen:
            continue
        seen.add(ref.event_id)
        refs.append(ref)
    refs.sort(key=lambda ref: ref.event_id)
    return refs


def _classify_incomplete(
    projection: ExecutionProjection,
    validation_failed: bool,
) -> IncompleteWork:
    if validation_failed:
        return IncompleteWork.RUN_FAILED
    if projection.outcome in {Outcome.BLOCKED, Outcome.REVIEW_REQUIRED}:
        return IncompleteWork.BLOCKED_OR_REVIEW
    if projection.lifecycle == Lifecycle.FAILED:
        return IncompleteWork.RUN_FAILED
    if projection.lifecycle in {Lifecycle.RUNNING, Lifecycle.UNKNOWN}:
        return IncompleteWork.RUN_INTERRUPTED
    if (
        projection.lifecycle == Lifecycle.COMPLETED
        and projection.validation != Validation.PASSED
    ):
        return IncompleteWork.ACCEPTANCE_UNPROVEN
    return IncompleteWork.NONE


def _has_governance_context_inconsistency(projection: ExecutionProjection) -> bool:
    context = projection.governance_context
    if context is None:
        return False
    return bool(context.inconsistencies)


def _scope_violated(
    projection: ExecutionProjection,
    signals: list[GovernanceSignal],
) -> bool:
    if projection.scope == Scope.VIOLATED:
        return True
    return bool(_signals_of_type(signals, _SCOPE_SIGNAL_TYPES))


def _validation_failure_signals(
    projection: ExecutionProjection,
    signals: list[GovernanceSignal],
) -> list[GovernanceSignal]:
    if projection.validation == Validation.FAILED:
        return [signal for signal in signals if signal.type in _VALIDATION_FAILURE_SIGNAL_TYPES]
    return _signals_of_type(signals, _VALIDATION_FAILURE_SIGNAL_TYPES)


def _governed_stop_signal(
    signals: list[GovernanceSignal],
) -> GovernanceSignal | None:
    present = _signals_of_type(signals, _GOVERNED_STOP_SIGNAL_TYPES)
    if not present:
        return None
    precedence = (
        SignalType.AUTHORITY_VIOLATION.value,
        SignalType.APPROVAL_DENIED.value,
        SignalType.BUDGET_EXCEEDED.value,
    )
    for signal_type in precedence:
        for signal in present:
            if signal.type == signal_type:
                return signal
    return present[0]


def _review_required_signal(
    signals: list[GovernanceSignal],
) -> GovernanceSignal | None:
    present = _signals_of_type(signals, _REVIEW_REQUIRED_SIGNAL_TYPES)
    if not present:
        return None
    precedence = (
        SignalType.HUMAN_REVIEW_REQUIRED.value,
        SignalType.APPROVAL_REQUIRED_UNRESOLVED.value,
        SignalType.BUDGET_UNKNOWN.value,
        SignalType.AUTHORITY_UNKNOWN.value,
    )
    for signal_type in precedence:
        for signal in present:
            if signal.type == signal_type:
                return signal
    return present[0]


def _explicit_sub_cause(signals: list[GovernanceSignal]) -> str:
    present = sorted(
        {signal.type for signal in signals if signal.type in _EXPLICIT_SUB_CAUSE_SIGNAL_TYPES}
    )
    if not present:
        return "unknown"
    return "+".join(present)


def _build(
    *,
    projection: ExecutionProjection,
    incomplete: IncompleteWork,
    root_cause: RootCause,
    root_cause_detail: str,
    risk: RiskLevel,
    next_action: NextAction,
    next_action_note: str,
    signals: list[GovernanceSignal],
) -> RunDiagnosis:
    return RunDiagnosis(
        run_id=projection.run_id,
        incomplete=incomplete,
        root_cause=root_cause,
        root_cause_detail=root_cause_detail,
        risk=risk,
        next_action=next_action,
        next_action_note=next_action_note,
        evidence_refs=_collect_evidence_refs(projection, signals),
    )


def diagnose_run(
    projection: ExecutionProjection,
    signals: list[GovernanceSignal],
) -> RunDiagnosis:
    """Project a deterministic advisory diagnosis from canonical run evidence.

    Classification is precedence-based and maps only explicit structured facts
    to a closed root-cause vocabulary. Missing acceptance evidence is never
    promoted to failed validation, unknown causes remain unknown, and no
    vendor/API/OOM cause is inferred without an explicit canonical fact.
    """
    validation_failed = bool(
        projection.validation == Validation.FAILED
        or _validation_failure_signals(projection, signals)
    )
    validation_failure_signals = _validation_failure_signals(projection, signals)
    incomplete = _classify_incomplete(projection, validation_failed)

    if _signals_of_type(signals, _EVIDENCE_INCONSISTENCY_SIGNAL_TYPES) or (
        _has_governance_context_inconsistency(projection)
    ):
        return _build(
            projection=projection,
            incomplete=incomplete,
            root_cause=RootCause.EVIDENCE_INCONSISTENT,
            root_cause_detail="evidence_inconsistent",
            risk=RiskLevel.HIGH,
            next_action=NextAction.HUMAN_REVIEW,
            next_action_note=(
                "Canonical facts contradict each other. Inspect the contradictory "
                "evidence before acting; no convenient fact was selected."
            ),
            signals=signals,
        )

    if _scope_violated(projection, signals):
        return _build(
            projection=projection,
            incomplete=incomplete,
            root_cause=RootCause.SCOPE_BOUNDARY,
            root_cause_detail="scope_violation",
            risk=RiskLevel.HIGH,
            next_action=NextAction.REPAIR_PACK_DEFINITION,
            next_action_note=(
                "Scope or attribution evidence is contaminated. Fix the pack scope "
                "evidence and attribution; do not widen scope and do not blindly "
                "retry the coder."
            ),
            signals=signals,
        )

    if validation_failed:
        repeated = any(
            signal.type == SignalType.REPEATED_VALIDATION_FAILURE.value
            for signal in validation_failure_signals
        )
        next_action = NextAction.HUMAN_REVIEW if repeated else NextAction.RETRY
        note = (
            "Repeated validation failure is proven by canonical facts; escalate to "
            "human review instead of another automatic retry."
            if repeated
            else "Failed validation is proven by canonical facts; fix the validated "
            "defect, then retry."
        )
        return _build(
            projection=projection,
            incomplete=incomplete,
            root_cause=RootCause.VALIDATION,
            root_cause_detail="validation_failed",
            risk=RiskLevel.HIGH,
            next_action=next_action,
            next_action_note=note,
            signals=signals,
        )

    governed_stop = _governed_stop_signal(signals)
    if governed_stop is not None:
        if governed_stop.type == SignalType.AUTHORITY_VIOLATION.value:
            risk = RiskLevel.CRITICAL
            next_action = NextAction.STOP
            note = "Run stopped by governance: authority violation. Stop and review."
        elif governed_stop.type == SignalType.APPROVAL_DENIED.value:
            risk = RiskLevel.MEDIUM
            next_action = NextAction.HUMAN_REVIEW
            note = (
                "Run stopped by governance: approval denied. "
                "Respect the denial; route to human review."
            )
        else:
            risk = RiskLevel.HIGH
            next_action = NextAction.REPAIR_RUNTIME
            note = (
                "Run stopped by governance: budget exceeded. "
                "Repair the budget; do not widen scope."
            )
        return _build(
            projection=projection,
            incomplete=incomplete,
            root_cause=RootCause.UNKNOWN,
            root_cause_detail=governed_stop.type,
            risk=risk,
            next_action=next_action,
            next_action_note=note,
            signals=signals,
        )

    review_required = _review_required_signal(signals)
    if review_required is not None:
        return _build(
            projection=projection,
            incomplete=incomplete,
            root_cause=RootCause.UNKNOWN,
            root_cause_detail=review_required.type,
            risk=RiskLevel.MEDIUM,
            next_action=NextAction.HUMAN_REVIEW,
            next_action_note=(
                "Review is required by canonical facts; route to human review."
            ),
            signals=signals,
        )

    if projection.lifecycle == Lifecycle.FAILED:
        sub_cause = _explicit_sub_cause(signals)
        note = (
            "Process supervision lost the run and no vendor cause is proven. "
            "Verify runtime supervision, then retry."
            if sub_cause == "unknown"
            else (
                "Process supervision lost the run; an explicit canonical fact names "
                f"{sub_cause}. Verify and retry."
            )
        )
        return _build(
            projection=projection,
            incomplete=incomplete,
            root_cause=RootCause.EXECUTION_RUNTIME_PROCESS_SUPERVISION,
            root_cause_detail=sub_cause,
            risk=RiskLevel.HIGH,
            next_action=NextAction.RETRY,
            next_action_note=note,
            signals=signals,
        )

    if (
        projection.lifecycle == Lifecycle.COMPLETED
        and projection.validation != Validation.PASSED
    ):
        return _build(
            projection=projection,
            incomplete=incomplete,
            root_cause=RootCause.UNPROVEN_COMPLETION,
            root_cause_detail="validation_evidence_missing",
            risk=RiskLevel.MEDIUM,
            next_action=NextAction.CONFIRM_RECONCILE,
            next_action_note=(
                "Run completed without accepted validation or acceptance evidence. "
                "Confirm or reconcile acceptance before trusting completion; this is "
                "not a validation failure."
            ),
            signals=signals,
        )

    if projection.lifecycle in {Lifecycle.RUNNING, Lifecycle.UNKNOWN}:
        return _build(
            projection=projection,
            incomplete=incomplete,
            root_cause=RootCause.UNKNOWN,
            root_cause_detail=f"lifecycle/{projection.lifecycle.value}",
            risk=RiskLevel.MEDIUM,
            next_action=NextAction.INSPECT,
            next_action_note=(
                "Run is not in a terminal lifecycle; inspect runtime state before "
                "concluding anything."
            ),
            signals=signals,
        )

    return _build(
        projection=projection,
        incomplete=incomplete,
        root_cause=RootCause.UNKNOWN,
        root_cause_detail="none",
        risk=RiskLevel.LOW,
        next_action=NextAction.NONE,
        next_action_note="No incomplete work and no failure class applies.",
        signals=signals,
    )


def render_diagnosis_json(diagnosis: RunDiagnosis) -> str:
    return diagnosis.model_dump_json(indent=2)


def render_diagnosis_markdown(diagnosis: RunDiagnosis) -> str:
    lines: list[str] = []

    lines.append("# Run Diagnosis")
    lines.append("")

    lines.append("## Diagnosis")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append(f"| Run ID | {diagnosis.run_id} |")
    lines.append(f"| Incomplete | {diagnosis.incomplete.value} |")
    lines.append(f"| Root Cause | {diagnosis.root_cause.value} |")
    lines.append(f"| Root Cause Detail | {diagnosis.root_cause_detail} |")
    lines.append(f"| Risk | {diagnosis.risk.value} |")
    lines.append(f"| Next Action | {diagnosis.next_action.value} |")
    lines.append("")

    if diagnosis.next_action_note:
        lines.append("## Advisory Note")
        lines.append("")
        lines.append(diagnosis.next_action_note)
        lines.append("")

    lines.append("## Evidence")
    lines.append("")
    if diagnosis.evidence_refs:
        for ref in diagnosis.evidence_refs:
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
