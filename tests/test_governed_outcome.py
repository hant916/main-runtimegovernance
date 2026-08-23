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
    ScopeOutcome,
    Validation,
)
from ailuros.execution_report import (
    aggregate_governed_outcomes,
    build_run_report,
    derive_governed_outcome,
    derive_scope_outcomes,
)
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
    scope_ref: str | None = None,
) -> GovernanceSignal:
    return GovernanceSignal.build(
        run_id=run_id,
        signal_type=signal_type,
        severity=severity,
        subject=subject,
        details=details or {},
        evidence_refs=evidence_refs or [],
        scope_ref=scope_ref,
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


# ── Deterministic multi-scope aggregation precedence ──────────────────────


def _scope_outcome(scope_ref: str | None, outcome: GovernedOutcome) -> ScopeOutcome:
    return ScopeOutcome(scope_ref=scope_ref, outcome=outcome)


def test_aggregate_single_clean_scope_is_clean() -> None:
    assert (
        aggregate_governed_outcomes([_scope_outcome("scope-a", GovernedOutcome.CLEAN_SUCCESS)])
        == GovernedOutcome.CLEAN_SUCCESS
    )


def test_aggregate_all_clean_scopes_is_clean() -> None:
    scoped = [
        _scope_outcome("scope-a", GovernedOutcome.CLEAN_SUCCESS),
        _scope_outcome("scope-b", GovernedOutcome.CLEAN_SUCCESS),
    ]
    assert aggregate_governed_outcomes(scoped) == GovernedOutcome.CLEAN_SUCCESS


def test_aggregate_failed_dominates_clean_scopes() -> None:
    scoped = [
        _scope_outcome("scope-a", GovernedOutcome.CLEAN_SUCCESS),
        _scope_outcome("scope-b", GovernedOutcome.FAILED),
    ]
    assert aggregate_governed_outcomes(scoped) == GovernedOutcome.FAILED


def test_aggregate_review_required_dominates_clean_scopes() -> None:
    scoped = [
        _scope_outcome("scope-a", GovernedOutcome.CLEAN_SUCCESS),
        _scope_outcome("scope-b", GovernedOutcome.REVIEW_REQUIRED),
    ]
    assert aggregate_governed_outcomes(scoped) == GovernedOutcome.REVIEW_REQUIRED


def test_aggregate_review_required_dominates_degraded_scopes() -> None:
    scoped = [
        _scope_outcome("scope-a", GovernedOutcome.DEGRADED_SUCCESS),
        _scope_outcome("scope-b", GovernedOutcome.REVIEW_REQUIRED),
    ]
    assert aggregate_governed_outcomes(scoped) == GovernedOutcome.REVIEW_REQUIRED


def test_aggregate_unknown_scope_prevents_clean_success() -> None:
    scoped = [
        _scope_outcome("scope-a", GovernedOutcome.CLEAN_SUCCESS),
        _scope_outcome("scope-b", GovernedOutcome.UNKNOWN),
    ]
    assert aggregate_governed_outcomes(scoped) == GovernedOutcome.UNKNOWN
    assert aggregate_governed_outcomes(scoped) != GovernedOutcome.CLEAN_SUCCESS


def test_aggregate_unknown_scope_prevents_degraded_success() -> None:
    scoped = [
        _scope_outcome("scope-a", GovernedOutcome.DEGRADED_SUCCESS),
        _scope_outcome("scope-b", GovernedOutcome.UNKNOWN),
    ]
    assert aggregate_governed_outcomes(scoped) == GovernedOutcome.UNKNOWN


def test_aggregate_degraded_success_prevails_over_clean() -> None:
    scoped = [
        _scope_outcome("scope-a", GovernedOutcome.CLEAN_SUCCESS),
        _scope_outcome("scope-b", GovernedOutcome.DEGRADED_SUCCESS),
    ]
    assert aggregate_governed_outcomes(scoped) == GovernedOutcome.DEGRADED_SUCCESS


def test_aggregate_unscoped_entry_is_a_valid_scope_input() -> None:
    scoped = [
        _scope_outcome(None, GovernedOutcome.REVIEW_REQUIRED),
        _scope_outcome("scope-a", GovernedOutcome.CLEAN_SUCCESS),
    ]
    assert aggregate_governed_outcomes(scoped) == GovernedOutcome.REVIEW_REQUIRED


def test_aggregate_empty_is_unknown() -> None:
    assert aggregate_governed_outcomes([]) == GovernedOutcome.UNKNOWN


def test_aggregate_is_deterministic() -> None:
    scoped = [
        _scope_outcome("scope-a", GovernedOutcome.CLEAN_SUCCESS),
        _scope_outcome("scope-b", GovernedOutcome.FAILED),
    ]
    first = aggregate_governed_outcomes(scoped)
    second = aggregate_governed_outcomes(list(reversed(scoped)))
    assert first == second


# ── Per-scope governed outcome derivation from scope-aware signals ────────


def test_scope_outcomes_group_by_scope_ref() -> None:
    proj = _make_projection()
    signals = [
        _make_signal(
            signal_type=SignalType.BUDGET_EXCEEDED,
            severity=Severity.HIGH,
            scope_ref="scope-a",
        ),
        _make_signal(
            signal_type=SignalType.BACKEND_FALLBACK,
            scope_ref="scope-b",
        ),
    ]
    outcomes = derive_scope_outcomes(proj, signals)
    by_scope = {entry.scope_ref: entry.outcome for entry in outcomes}
    assert by_scope == {
        "scope-a": GovernedOutcome.FAILED,
        "scope-b": GovernedOutcome.DEGRADED_SUCCESS,
    }


def test_scope_outcome_uses_run_level_facts_as_floor() -> None:
    proj = _make_projection(
        lifecycle=Lifecycle.FAILED,
        outcome=Outcome.FAILED,
        validation=Validation.FAILED,
    )
    signals = [
        _make_signal(signal_type=SignalType.BACKEND_FALLBACK, scope_ref="scope-a")
    ]
    outcomes = derive_scope_outcomes(proj, signals)
    assert outcomes == [
        ScopeOutcome(scope_ref="scope-a", outcome=GovernedOutcome.FAILED)
    ]


def test_scope_outcomes_include_unscoped_signals() -> None:
    proj = _make_projection()
    signals = [
        _make_signal(signal_type=SignalType.BACKEND_FALLBACK, scope_ref=None),
    ]
    outcomes = derive_scope_outcomes(proj, signals)
    assert outcomes == [
        ScopeOutcome(scope_ref=None, outcome=GovernedOutcome.DEGRADED_SUCCESS)
    ]


def test_scope_outcomes_empty_without_signals() -> None:
    proj = _make_projection()
    assert derive_scope_outcomes(proj, []) == []


def test_scope_outcomes_missing_scope_is_not_inferred_clean() -> None:
    proj = _make_projection()
    outcomes = derive_scope_outcomes(proj, [])
    assert not any(entry.outcome == GovernedOutcome.CLEAN_SUCCESS for entry in outcomes)


def test_report_exposes_scope_outcomes_and_aggregate() -> None:
    proj = _make_projection()
    signals = [
        _make_signal(
            signal_type=SignalType.BUDGET_EXCEEDED,
            severity=Severity.HIGH,
            scope_ref="scope-a",
        ),
        _make_signal(
            signal_type=SignalType.BACKEND_FALLBACK,
            scope_ref="scope-b",
        ),
    ]
    report = build_run_report(proj, signals)
    assert report.aggregate_governed_outcome == GovernedOutcome.FAILED.value
    assert len(report.scope_outcomes) == 2
    by_scope = {entry.scope_ref: entry.outcome.value for entry in report.scope_outcomes}
    assert by_scope == {
        "scope-a": GovernedOutcome.FAILED.value,
        "scope-b": GovernedOutcome.DEGRADED_SUCCESS.value,
    }


def test_report_single_scope_aggregate_matches_governed_outcome() -> None:
    proj = _make_projection()
    signals = [
        _make_signal(
            signal_type=SignalType.BACKEND_FALLBACK,
            scope_ref="scope-a",
        )
    ]
    report = build_run_report(proj, signals)
    assert report.governed_outcome == GovernedOutcome.DEGRADED_SUCCESS.value
    assert report.aggregate_governed_outcome == report.governed_outcome
    assert len(report.scope_outcomes) == 1
    assert report.scope_outcomes[0].scope_ref == "scope-a"
