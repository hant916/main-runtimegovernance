from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from ailuros.core.execution import (
    CoverageState,
    DecisionSummary,
    EvidenceRef,
    ExecutionProjection,
    GovernanceCoverage,
    GovernedOutcome,
    Lifecycle,
    Outcome,
    Scope,
    Validation,
)
from ailuros.execution_report import (
    GovernedExecutionResult,
    build_governed_execution_result,
    render_governed_execution_result_json,
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
    scope_ref: str | None = None,
    decisions: list[DecisionSummary] | None = None,
    evidence_refs: list[EvidenceRef] | None = None,
) -> ExecutionProjection:
    now = datetime.now(UTC)
    return ExecutionProjection(
        run_id=run_id,
        source="test",
        schema_version="1.0",
        lifecycle=lifecycle,
        outcome=outcome,
        validation=validation,
        scope=scope,
        scope_ref=scope_ref,
        started_at=now,
        completed_at=now + timedelta(minutes=5),
        decisions=decisions or [],
        evidence_refs=evidence_refs or [],
    )


def _make_signal(
    *,
    signal_type: SignalType,
    run_id: str = "run-1",
    severity: Severity = Severity.MEDIUM,
    subject: str = "test",
    evidence_refs: list[EvidenceRef] | None = None,
) -> GovernanceSignal:
    return GovernanceSignal.build(
        run_id=run_id,
        signal_type=signal_type,
        severity=severity,
        subject=subject,
        details={},
        evidence_refs=evidence_refs or [],
    )


class TestGovernedExecutionResultContract:
    def test_requires_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            GovernedExecutionResult()

    def test_extra_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            GovernedExecutionResult(
                run_id="r1",
                lifecycle=Lifecycle.COMPLETED,
                validation=Validation.PASSED,
                scope=Scope.CLEAN,
                native_outcome=Outcome.SUCCESS,
                governed_outcome=GovernedOutcome.CLEAN_SUCCESS,
                extra_field="bad",
            )

    def test_scope_ref_defaults_none(self) -> None:
        result = GovernedExecutionResult(
            run_id="r1",
            lifecycle=Lifecycle.COMPLETED,
            validation=Validation.PASSED,
            scope=Scope.CLEAN,
            native_outcome=Outcome.SUCCESS,
            governed_outcome=GovernedOutcome.CLEAN_SUCCESS,
        )
        assert result.scope_ref is None

    def test_scope_ref_preserved(self) -> None:
        result = GovernedExecutionResult(
            run_id="r1",
            scope_ref="scope-a",
            lifecycle=Lifecycle.COMPLETED,
            validation=Validation.PASSED,
            scope=Scope.CLEAN,
            native_outcome=Outcome.SUCCESS,
            governed_outcome=GovernedOutcome.CLEAN_SUCCESS,
        )
        assert result.scope_ref == "scope-a"

    def test_scope_ref_malformed_rejected(self) -> None:
        with pytest.raises(ValidationError):
            GovernedExecutionResult(
                run_id="r1",
                scope_ref=42,
                lifecycle=Lifecycle.COMPLETED,
                validation=Validation.PASSED,
                scope=Scope.CLEAN,
                native_outcome=Outcome.SUCCESS,
                governed_outcome=GovernedOutcome.CLEAN_SUCCESS,
            )


class TestBuildGovernedExecutionResult:
    def test_scoped_projection_carries_scope_identity(self) -> None:
        proj = _make_projection(scope_ref="scope-a")
        result = build_governed_execution_result(proj, [])
        assert result.run_id == "run-1"
        assert result.scope_ref == "scope-a"
        assert result.lifecycle == Lifecycle.COMPLETED
        assert result.scope == Scope.CLEAN

    def test_unscoped_projection_scope_ref_none(self) -> None:
        proj = _make_projection()
        result = build_governed_execution_result(proj, [])
        assert result.scope_ref is None

    def test_native_outcome_derived_from_lifecycle_and_decisions(self) -> None:
        proj = _make_projection(
            lifecycle=Lifecycle.COMPLETED,
            outcome=Outcome.REVIEW_REQUIRED,
            decisions=[
                DecisionSummary(
                    domain="gov", decision="block",
                    projected_domain="execution_control",
                ),
            ],
        )
        result = build_governed_execution_result(proj, [])
        assert result.native_outcome == Outcome.BLOCKED
        assert result.governed_outcome == GovernedOutcome.REVIEW_REQUIRED

    def test_governed_outcome_derived_from_canonical_signals(self) -> None:
        proj = _make_projection()
        signals = [_make_signal(signal_type=SignalType.BACKEND_FALLBACK)]
        result = build_governed_execution_result(proj, signals)
        assert result.governed_outcome == GovernedOutcome.DEGRADED_SUCCESS

    def test_unknown_state_projects_unknown(self) -> None:
        proj = _make_projection(
            lifecycle=Lifecycle.RUNNING,
            outcome=Outcome.UNKNOWN,
            validation=Validation.NOT_RUN,
            scope=Scope.UNKNOWN,
        )
        result = build_governed_execution_result(proj, [])
        assert result.lifecycle == Lifecycle.RUNNING
        assert result.native_outcome == Outcome.UNKNOWN
        assert result.governed_outcome == GovernedOutcome.UNKNOWN

    def test_coverage_transferred(self) -> None:
        coverage = GovernanceCoverage(
            authority=CoverageState.NOT_APPLICABLE,
            scope=CoverageState.EVALUATED,
        )
        proj = _make_projection(scope=Scope.VIOLATED)
        proj.governance_coverage = coverage
        result = build_governed_execution_result(proj, [])
        assert result.coverage == coverage

    def test_signals_summarized_without_producer_details(self) -> None:
        refs = [EvidenceRef(event_id="evt-1")]
        proj = _make_projection()
        signals = [
            _make_signal(
                signal_type=SignalType.SCOPE_VIOLATION,
                severity=Severity.CRITICAL,
                subject="scope",
                evidence_refs=refs,
            )
        ]
        result = build_governed_execution_result(proj, signals)
        assert len(result.signals) == 1
        summary = result.signals[0]
        assert summary.type == "scope_violation"
        assert summary.severity == "critical"
        assert summary.subject == "scope"
        assert summary.evidence_refs == refs

    def test_evidence_refs_transferred(self) -> None:
        refs = [_make_evidence_ref("e1"), _make_evidence_ref("e2", artifact="a.json")]
        proj = _make_projection(evidence_refs=refs)
        result = build_governed_execution_result(proj, [])
        assert result.evidence_refs == refs

    def test_deterministic_build(self) -> None:
        proj = _make_projection(scope_ref="scope-a")
        signals = [_make_signal(signal_type=SignalType.BACKEND_FALLBACK)]
        first = build_governed_execution_result(proj, signals)
        second = build_governed_execution_result(proj, signals)
        assert first.model_dump() == second.model_dump()


class TestRenderGovernedExecutionResultJson:
    def test_renders_valid_json(self) -> None:
        proj = _make_projection(scope_ref="scope-a")
        result = build_governed_execution_result(proj, [])
        parsed = json.loads(render_governed_execution_result_json(result))
        assert parsed["run_id"] == "run-1"
        assert parsed["scope_ref"] == "scope-a"
        assert parsed["lifecycle"] == "completed"
        assert parsed["validation"] == "passed"
        assert parsed["scope"] == "clean"
        assert parsed["native_outcome"] == "success"
        assert parsed["governed_outcome"] == "clean_success"

    def test_scoped_and_unscoped_outputs_differ_only_by_scope(self) -> None:
        scoped = build_governed_execution_result(_make_projection(scope_ref="scope-a"), [])
        unscoped = build_governed_execution_result(_make_projection(), [])
        scoped_data = json.loads(render_governed_execution_result_json(scoped))
        unscoped_data = json.loads(render_governed_execution_result_json(unscoped))
        assert scoped_data["scope_ref"] == "scope-a"
        assert unscoped_data["scope_ref"] is None
        scoped_data["scope_ref"] = None
        assert scoped_data == unscoped_data

    def test_unknown_state_renders_stably(self) -> None:
        proj = _make_projection(
            lifecycle=Lifecycle.RUNNING,
            outcome=Outcome.UNKNOWN,
            validation=Validation.NOT_RUN,
            scope=Scope.UNKNOWN,
        )
        result = build_governed_execution_result(proj, [])
        parsed = json.loads(render_governed_execution_result_json(result))
        assert parsed["governed_outcome"] == "unknown"
        assert parsed["native_outcome"] == "unknown"

    def test_stable_ordering_across_renders(self) -> None:
        proj = _make_projection()
        signals = [_make_signal(signal_type=SignalType.BACKEND_FALLBACK)]
        result = build_governed_execution_result(proj, signals)
        out1 = render_governed_execution_result_json(result)
        out2 = render_governed_execution_result_json(result)
        assert out1 == out2

    def test_no_noncanonical_timestamps_or_details(self) -> None:
        proj = _make_projection()
        signals = [
            _make_signal(
                signal_type=SignalType.SCOPE_VIOLATION,
                severity=Severity.CRITICAL,
                subject="scope",
                evidence_refs=[_make_evidence_ref("evt-1")],
            )
        ]
        result = build_governed_execution_result(proj, signals)
        output = render_governed_execution_result_json(result)
        assert "created_at" not in output
        assert "details" not in output
        assert "rule_version" not in output
        assert "evt-1" in output


def _make_evidence_ref(
    event_id: str,
    artifact: str | None = None,
    pointer: str | None = None,
) -> EvidenceRef:
    return EvidenceRef(event_id=event_id, artifact=artifact, pointer=pointer)