from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ailuros.core.execution import (
    DecisionSummary,
    EvidenceRef,
    ExecutionProjection,
    GovernedOutcome,
    Lifecycle,
    Outcome,
    Scope,
    Validation,
)
from ailuros.execution_report import build_run_report, derive_governed_outcome
from ailuros.models.common import Severity
from ailuros.signals import GovernanceSignal, SignalType


def _make_projection(
    *,
    run_id: str = "run-1",
    lifecycle: Lifecycle = Lifecycle.COMPLETED,
    outcome: Outcome = Outcome.SUCCESS,
    validation: Validation = Validation.PASSED,
    scope: Scope = Scope.CLEAN,
    decisions: list[DecisionSummary] | None = None,
) -> ExecutionProjection:
    now = datetime.now(UTC)
    return ExecutionProjection(
        run_id=run_id,
        source="test",
        schema_version="1.0.0",
        lifecycle=lifecycle,
        outcome=outcome,
        validation=validation,
        scope=scope,
        started_at=now,
        completed_at=now + timedelta(minutes=5),
        decisions=decisions or [],
    )


def _make_signal(
    *,
    signal_type: SignalType,
    run_id: str = "run-1",
    severity: Severity = Severity.MEDIUM,
    subject: str = "test",
    evidence_refs: list[EvidenceRef] | None = None,
    details: dict[str, object] | None = None,
) -> GovernanceSignal:
    return GovernanceSignal.build(
        run_id=run_id,
        signal_type=signal_type,
        severity=severity,
        subject=subject,
        details=details or {},
        evidence_refs=evidence_refs or [],
    )


# ── CLEAN_SUCCESS requires sufficient affirmative clean evidence ───────────


def test_clean_completion_with_passed_validation_is_clean_success() -> None:
    proj = _make_projection()
    outcome, reasons = derive_governed_outcome(proj, [])
    assert outcome == GovernedOutcome.CLEAN_SUCCESS
    assert reasons == []


def test_exit_success_with_no_terminal_validation_proof_is_not_clean_success() -> None:
    proj = _make_projection(validation=Validation.NOT_RUN)
    outcome, _ = derive_governed_outcome(proj, [])
    assert outcome != GovernedOutcome.CLEAN_SUCCESS
    assert outcome == GovernedOutcome.DEGRADED_SUCCESS


# ── Partial validation + successful completion => DEGRADED_SUCCESS ─────────


def test_partial_validation_with_success_is_degraded_success() -> None:
    proj = _make_projection(validation=Validation.PARTIAL)
    outcome, reasons = derive_governed_outcome(proj, [])
    assert outcome == GovernedOutcome.DEGRADED_SUCCESS
    assert reasons


def test_nonblocking_fallback_signal_with_success_is_degraded_success() -> None:
    proj = _make_projection()
    signals = [_make_signal(signal_type=SignalType.BACKEND_FALLBACK)]
    outcome, reasons = derive_governed_outcome(proj, signals)
    assert outcome == GovernedOutcome.DEGRADED_SUCCESS
    assert reasons[0].code == SignalType.BACKEND_FALLBACK.value


# ── Required human review => REVIEW_REQUIRED, first-class ──────────────────


def test_review_required_outcome_projects_review_required() -> None:
    proj = _make_projection(outcome=Outcome.REVIEW_REQUIRED)
    outcome, _ = derive_governed_outcome(proj, [])
    assert outcome == GovernedOutcome.REVIEW_REQUIRED


def test_human_review_signal_projects_review_required() -> None:
    proj = _make_projection()
    signals = [_make_signal(signal_type=SignalType.HUMAN_REVIEW_REQUIRED)]
    outcome, _ = derive_governed_outcome(proj, signals)
    assert outcome == GovernedOutcome.REVIEW_REQUIRED


def test_authority_unknown_signal_projects_review_required() -> None:
    proj = _make_projection()
    signals = [_make_signal(signal_type=SignalType.AUTHORITY_UNKNOWN)]
    outcome, _ = derive_governed_outcome(proj, signals)
    assert outcome == GovernedOutcome.REVIEW_REQUIRED


def test_unresolved_required_approval_projects_review_required() -> None:
    proj = _make_projection()
    ref = EvidenceRef(event_id="evt-approval-required")
    signals = [
        _make_signal(
            signal_type=SignalType.APPROVAL_REQUIRED_UNRESOLVED,
            evidence_refs=[ref],
        )
    ]

    outcome, reasons = derive_governed_outcome(proj, signals)

    assert outcome == GovernedOutcome.REVIEW_REQUIRED
    assert reasons[0].code == SignalType.APPROVAL_REQUIRED_UNRESOLVED.value
    assert reasons[0].evidence_refs == [ref]


def test_required_unknown_budget_cannot_be_clean_success() -> None:
    proj = _make_projection()
    signals = [_make_signal(signal_type=SignalType.BUDGET_UNKNOWN)]

    outcome, _ = derive_governed_outcome(proj, signals)

    assert outcome == GovernedOutcome.REVIEW_REQUIRED
    assert outcome != GovernedOutcome.CLEAN_SUCCESS


def test_review_required_cannot_be_overwritten_by_source_success() -> None:
    proj = _make_projection(outcome=Outcome.REVIEW_REQUIRED, validation=Validation.PASSED)
    outcome, _ = derive_governed_outcome(proj, [])
    assert outcome == GovernedOutcome.REVIEW_REQUIRED


# ── Authority violation / explicit failure => FAILED ────────────────────────


def test_authority_violation_signal_projects_failed() -> None:
    proj = _make_projection()
    signals = [_make_signal(signal_type=SignalType.AUTHORITY_VIOLATION, severity=Severity.CRITICAL)]
    outcome, reasons = derive_governed_outcome(proj, signals)
    assert outcome == GovernedOutcome.FAILED
    assert reasons[0].code == SignalType.AUTHORITY_VIOLATION.value


def test_budget_exceeded_signal_projects_failed_with_evidence() -> None:
    proj = _make_projection()
    ref = EvidenceRef(event_id="evt-budget-exceeded")
    signals = [
        _make_signal(
            signal_type=SignalType.BUDGET_EXCEEDED,
            severity=Severity.HIGH,
            evidence_refs=[ref],
        )
    ]

    outcome, reasons = derive_governed_outcome(proj, signals)

    assert outcome == GovernedOutcome.FAILED
    assert outcome not in {
        GovernedOutcome.CLEAN_SUCCESS,
        GovernedOutcome.DEGRADED_SUCCESS,
    }
    assert reasons[0].code == SignalType.BUDGET_EXCEEDED.value
    assert reasons[0].evidence_refs == [ref]


def test_approval_denied_with_observed_action_projects_failed() -> None:
    proj = _make_projection()
    signals = [
        _make_signal(
            signal_type=SignalType.APPROVAL_DENIED,
            severity=Severity.HIGH,
            details={"action": "deploy"},
        )
    ]

    outcome, _ = derive_governed_outcome(proj, signals)

    assert outcome == GovernedOutcome.FAILED


def test_approval_denial_without_observed_action_is_not_blocking() -> None:
    proj = _make_projection()
    signals = [_make_signal(signal_type=SignalType.APPROVAL_DENIED, severity=Severity.HIGH)]

    outcome, _ = derive_governed_outcome(proj, signals)

    assert outcome == GovernedOutcome.CLEAN_SUCCESS


def test_native_failed_outcome_projects_failed() -> None:
    proj = _make_projection(lifecycle=Lifecycle.FAILED, outcome=Outcome.FAILED)
    outcome, _ = derive_governed_outcome(proj, [])
    assert outcome == GovernedOutcome.FAILED


def test_authority_violation_cannot_produce_clean_or_degraded_success() -> None:
    proj = _make_projection()
    signals = [
        _make_signal(signal_type=SignalType.AUTHORITY_VIOLATION, severity=Severity.CRITICAL),
        _make_signal(signal_type=SignalType.BACKEND_FALLBACK),
    ]
    outcome, _ = derive_governed_outcome(proj, signals)
    assert outcome not in {GovernedOutcome.CLEAN_SUCCESS, GovernedOutcome.DEGRADED_SUCCESS}
    assert outcome == GovernedOutcome.FAILED


def test_failed_takes_precedence_over_review_required_signal() -> None:
    proj = _make_projection()
    signals = [
        _make_signal(signal_type=SignalType.AUTHORITY_VIOLATION, severity=Severity.CRITICAL),
        _make_signal(signal_type=SignalType.HUMAN_REVIEW_REQUIRED),
    ]
    outcome, _ = derive_governed_outcome(proj, signals)
    assert outcome == GovernedOutcome.FAILED


# ── Missing terminal evidence => UNKNOWN, never CLEAN_SUCCESS ──────────────


def test_missing_terminal_evidence_projects_unknown() -> None:
    proj = _make_projection(lifecycle=Lifecycle.RUNNING, outcome=Outcome.UNKNOWN)
    outcome, _ = derive_governed_outcome(proj, [])
    assert outcome == GovernedOutcome.UNKNOWN
    assert outcome != GovernedOutcome.CLEAN_SUCCESS


def test_unknown_outcome_with_completed_lifecycle_is_not_clean_success() -> None:
    proj = _make_projection(outcome=Outcome.UNKNOWN)
    outcome, _ = derive_governed_outcome(proj, [])
    assert outcome != GovernedOutcome.CLEAN_SUCCESS


# ── Determinism ──────────────────────────────────────────────────────────


def test_governed_outcome_is_deterministic_for_identical_evidence() -> None:
    proj = _make_projection()
    signals = [_make_signal(signal_type=SignalType.BACKEND_FALLBACK)]
    first, _ = derive_governed_outcome(proj, signals)
    second, _ = derive_governed_outcome(proj, signals)
    assert first == second


# ── Native/source outcome remains visible alongside governed outcome ───────


def test_run_report_exposes_native_and_governed_outcome_together() -> None:
    proj = _make_projection()
    signals = [_make_signal(signal_type=SignalType.BACKEND_FALLBACK)]
    report = build_run_report(proj, signals)
    assert report.outcome == Outcome.SUCCESS.value
    assert report.governed_outcome == GovernedOutcome.DEGRADED_SUCCESS.value


def test_run_report_governed_outcome_reasons_carry_evidence_refs() -> None:
    proj = _make_projection()
    signals = [
        _make_signal(
            signal_type=SignalType.AUTHORITY_VIOLATION,
            severity=Severity.CRITICAL,
            evidence_refs=[EvidenceRef(event_id="evt-1")],
        )
    ]
    report = build_run_report(proj, signals)
    assert report.governed_outcome == GovernedOutcome.FAILED.value
    assert report.governed_outcome_reasons[0].evidence_refs[0].event_id == "evt-1"
