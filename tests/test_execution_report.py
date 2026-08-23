from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from ailuros.core.execution import (
    ChangeSummary,
    CoverageState,
    DecisionSummary,
    EvidenceRef,
    ExecutionProjection,
    Lifecycle,
    Outcome,
    RoleSummary,
    Scope,
    Validation,
)
from ailuros.execution_report import (
    RunReport,
    SignalSummary,
    build_run_report,
    render_run_report_json,
    render_run_report_markdown,
)
from ailuros.models.common import Severity
from ailuros.projection import build_execution_projection
from ailuros.signals import GovernanceSignal, SignalType


def _make_projection(
    *,
    run_id: str = "run-1",
    lifecycle: Lifecycle = Lifecycle.COMPLETED,
    outcome: Outcome = Outcome.SUCCESS,
    validation: Validation = Validation.PASSED,
    scope: Scope = Scope.CLEAN,
    decisions: list[DecisionSummary] | None = None,
    evidence_refs: list[EvidenceRef] | None = None,
    changes: list[ChangeSummary] | None = None,
    roles: list[RoleSummary] | None = None,
    step_count: int = 3,
    decision_count: int = 2,
    event_count: int = 10,
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
        step_count=step_count,
        decision_count=decision_count,
        event_count=event_count,
        decisions=decisions or [],
        evidence_refs=evidence_refs or [],
        changes=changes or [],
        roles=roles or [],
    )


def _make_signal(
    *,
    run_id: str = "run-1",
    signal_type: SignalType = SignalType.VALIDATION_FAILURE,
    severity: Severity = Severity.HIGH,
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


def _make_ref(
    event_id: str,
    artifact: str | None = None,
    pointer: str | None = None,
) -> EvidenceRef:
    return EvidenceRef(event_id=event_id, artifact=artifact, pointer=pointer)


def _projection_event(
    event_id: str,
    event_type: str,
    timestamp: datetime,
    payload: dict,
) -> dict:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "timestamp": timestamp,
        "payload": payload,
    }


class TestBuildRunReport:
    def test_headline_fields_reflect_projection(self) -> None:
        proj = _make_projection(
            lifecycle=Lifecycle.COMPLETED,
            outcome=Outcome.SUCCESS,
            validation=Validation.PASSED,
            scope=Scope.CLEAN,
        )
        report = build_run_report(proj, [])
        assert report.lifecycle == "completed"
        assert report.outcome == "success"
        assert report.validation == "passed"
        assert report.scope == "clean"

    def test_why_stopped_uses_execution_control_decision(self) -> None:
        proj = _make_projection(
            lifecycle=Lifecycle.FAILED,
            outcome=Outcome.FAILED,
            decisions=[
                DecisionSummary(
                    domain="governance",
                    decision="block",
                    projected_domain="execution_control",
                ),
            ],
        )
        report = build_run_report(proj, [])
        assert "execution_control" in report.why_stopped
        assert "block" in report.why_stopped

    def test_why_stopped_falls_back_to_lifecycle(self) -> None:
        proj = _make_projection(
            lifecycle=Lifecycle.FAILED,
            outcome=Outcome.FAILED,
        )
        report = build_run_report(proj, [])
        assert report.why_stopped == "lifecycle: failed"

    def test_why_stopped_falls_back_to_review_required_outcome(self) -> None:
        proj = _make_projection(
            lifecycle=Lifecycle.COMPLETED,
            outcome=Outcome.REVIEW_REQUIRED,
        )
        report = build_run_report(proj, [])
        assert report.why_stopped == "outcome: review_required"

    def test_why_stopped_falls_back_to_blocked_outcome(self) -> None:
        proj = _make_projection(
            lifecycle=Lifecycle.FAILED,
            outcome=Outcome.BLOCKED,
        )
        report = build_run_report(proj, [])
        assert report.why_stopped == "outcome: blocked"

    def test_why_stopped_falls_back_to_signals(self) -> None:
        proj = _make_projection(
            lifecycle=Lifecycle.RUNNING,
            outcome=Outcome.UNKNOWN,
        )
        sig = _make_signal(signal_type=SignalType.BACKEND_UNAVAILABLE, severity=Severity.HIGH)
        report = build_run_report(proj, [sig])
        assert "backend_unavailable" in report.why_stopped

    def test_why_stopped_unknown_when_nothing_available(self) -> None:
        proj = _make_projection(
            lifecycle=Lifecycle.RUNNING,
            outcome=Outcome.UNKNOWN,
        )
        report = build_run_report(proj, [])
        assert report.why_stopped == "unknown"

    def test_signal_summaries_populated(self) -> None:
        refs = [_make_ref("evt-1")]
        sig = _make_signal(
            signal_type=SignalType.SCOPE_VIOLATION,
            severity=Severity.CRITICAL,
            subject="scope",
            evidence_refs=refs,
        )
        proj = _make_projection()
        report = build_run_report(proj, [sig])
        assert len(report.signal_summaries) == 1
        ss = report.signal_summaries[0]
        assert ss.type == "scope_violation"
        assert ss.severity == "critical"
        assert ss.subject == "scope"
        assert len(ss.evidence_refs) == 1
        assert ss.evidence_refs[0].event_id == "evt-1"

    def test_decision_reasons_aggregated(self) -> None:
        proj = _make_projection(
            decisions=[
                DecisionSummary(
                    domain="gov", decision="block",
                    projected_domain="execution_control",
                ),
                DecisionSummary(
                    domain="gov", decision="allow",
                    projected_domain="source_preserved_unknown",
                ),
            ],
        )
        report = build_run_report(proj, [])
        assert len(report.decision_reasons) == 2
        assert "execution_control/block" in report.decision_reasons
        assert "source_preserved_unknown/allow" in report.decision_reasons

    def test_timeline_counts_transferred(self) -> None:
        proj = _make_projection(step_count=5, decision_count=8, event_count=20)
        report = build_run_report(proj, [])
        assert report.step_count == 5
        assert report.decision_count == 8
        assert report.event_count == 20

    def test_evidence_refs_transferred(self) -> None:
        refs = [_make_ref("e1"), _make_ref("e2", artifact="a.json")]
        proj = _make_projection(evidence_refs=refs)
        report = build_run_report(proj, [])
        assert len(report.evidence_refs) == 2

    def test_changes_and_roles_transferred(self) -> None:
        proj = _make_projection(
            changes=[ChangeSummary(description="added file")],
            roles=[RoleSummary(name="planner")],
        )
        report = build_run_report(proj, [])
        assert len(report.changes) == 1
        assert report.changes[0].description == "added file"
        assert len(report.roles) == 1
        assert report.roles[0].name == "planner"

    def test_absent_evidence_keeps_coverage_unknown_without_signals(self) -> None:
        now = datetime.now(UTC)
        projection = build_execution_projection(
            "run-coverage-unknown",
            "test",
            [
                _projection_event("start", "run_started", now, {}),
                _projection_event("end", "run_completed", now, {}),
            ],
        )
        report = build_run_report(projection, [])
        assert report.governance_coverage.model_dump() == {
            "authority": "unknown",
            "approval": "unknown",
            "budget": "unknown",
            "validation": "unknown",
            "scope": "unknown",
        }

    def test_present_governance_evidence_marks_coverage_evaluated(self) -> None:
        now = datetime.now(UTC)
        projection = build_execution_projection(
            "run-coverage-evaluated",
            "test",
            [
                _projection_event(
                    "approval",
                    "approval_evidence",
                    now,
                    {"subject": "deploy", "decision": "approved"},
                ),
                _projection_event(
                    "budget",
                    "budget_evidence",
                    now,
                    {"subject": "deploy", "unit": "tokens", "limit": 10, "consumed": 5},
                ),
                _projection_event(
                    "authority",
                    "authority_evidence",
                    now,
                    {"actor": "agent", "status": "authorized"},
                ),
                _projection_event(
                    "validation", "project_validation", now, {"status": "passed"}
                ),
                _projection_event("scope", "project_scope", now, {"status": "clean"}),
            ],
        )
        report = build_run_report(projection, [])
        coverage_values = set(report.governance_coverage.model_dump().values())
        assert coverage_values == {CoverageState.EVALUATED.value}

    def test_required_false_evidence_marks_supported_dimensions_not_applicable(self) -> None:
        now = datetime.now(UTC)
        projection = build_execution_projection(
            "run-coverage-not-applicable",
            "test",
            [
                _projection_event(
                    "approval",
                    "approval_evidence",
                    now,
                    {"subject": "deploy", "required": False},
                ),
                _projection_event(
                    "budget",
                    "budget_evidence",
                    now,
                    {"subject": "deploy", "unit": "tokens", "required": False},
                ),
                _projection_event(
                    "authority",
                    "authority_evidence",
                    now,
                    {"actor": "agent", "required": False},
                ),
            ],
        )
        report = build_run_report(projection, [])
        assert report.governance_coverage.authority == CoverageState.NOT_APPLICABLE
        assert report.governance_coverage.approval == CoverageState.NOT_APPLICABLE
        assert report.governance_coverage.budget == CoverageState.NOT_APPLICABLE
        assert report.governance_coverage.validation == CoverageState.UNKNOWN
        assert report.governance_coverage.scope == CoverageState.UNKNOWN

    def test_mixed_scope_signals_expose_scope_outcomes_and_aggregate(self) -> None:
        now = datetime.now(UTC)
        projection = build_execution_projection(
            "run-mixed-scope",
            "test",
            [
                _projection_event("start", "run_started", now, {}),
                _projection_event("end", "run_completed", now, {}),
            ],
        )
        signals = [
            _make_signal(
                signal_type=SignalType.BUDGET_EXCEEDED,
                severity=Severity.HIGH,
                subject="budget",
                evidence_refs=[_make_ref("e1")],
            ),
            _make_signal(
                signal_type=SignalType.BACKEND_FALLBACK,
                severity=Severity.MEDIUM,
                subject="backend",
                evidence_refs=[_make_ref("e2")],
            ),
        ]
        signals[0].scope_ref = "scope-a"
        signals[1].scope_ref = "scope-b"
        report = build_run_report(projection, signals)
        assert report.aggregate_governed_outcome == "failed"
        assert len(report.scope_outcomes) == 2
        by_scope = {entry.scope_ref: entry.outcome.value for entry in report.scope_outcomes}
        assert by_scope == {
            "scope-a": "failed",
            "scope-b": "degraded_success",
        }

    def test_clean_single_scope_report_aggregate_matches_governed_outcome(self) -> None:
        proj = _make_projection()
        report = build_run_report(proj, [])
        assert report.governed_outcome == "clean_success"
        assert report.aggregate_governed_outcome == "clean_success"
        assert report.scope_outcomes == []


class TestOutcomeReasons:
    def test_native_outcome_derived_from_lifecycle(self) -> None:
        proj = _make_projection(
            lifecycle=Lifecycle.COMPLETED,
            outcome=Outcome.SUCCESS,
        )
        report = build_run_report(proj, [])
        assert report.native_outcome == "success"

    def test_native_outcome_preserved_separately_from_outcome(self) -> None:
        proj = _make_projection(
            lifecycle=Lifecycle.COMPLETED,
            outcome=Outcome.REVIEW_REQUIRED,
        )
        report = build_run_report(proj, [])
        assert report.native_outcome == "success"
        assert report.outcome == "review_required"

    def test_approval_budget_signal_becomes_outcome_reason(self) -> None:
        ref = _make_ref("evt-a")
        sig = _make_signal(
            signal_type=SignalType.BUDGET_EXCEEDED,
            severity=Severity.HIGH,
            subject="budget",
            evidence_refs=[ref],
        )
        proj = _make_projection(lifecycle=Lifecycle.COMPLETED, outcome=Outcome.FAILED)
        report = build_run_report(proj, [sig])
        assert len(report.outcome_reasons) == 1
        assert report.outcome_reasons[0].code == "budget_exceeded"
        assert report.outcome_reasons[0].evidence_refs == [ref]

    def test_non_approval_budget_signal_is_not_an_outcome_reason(self) -> None:
        sig = _make_signal(
            signal_type=SignalType.SCOPE_VIOLATION,
            severity=Severity.CRITICAL,
            subject="scope",
        )
        proj = _make_projection()
        report = build_run_report(proj, [sig])
        assert report.outcome_reasons == []

    def test_all_approval_budget_signal_types_are_reason_codes(self) -> None:
        proj = _make_projection()
        signals = [
            _make_signal(signal_type=SignalType.APPROVAL_DENIED, severity=Severity.HIGH),
            _make_signal(
                signal_type=SignalType.APPROVAL_REQUIRED_UNRESOLVED,
                severity=Severity.MEDIUM,
            ),
            _make_signal(signal_type=SignalType.BUDGET_UNKNOWN, severity=Severity.MEDIUM),
        ]
        report = build_run_report(proj, signals)
        codes = {reason.code for reason in report.outcome_reasons}
        assert codes == {
            "approval_denied",
            "approval_required_unresolved",
            "budget_unknown",
        }


class TestRenderRunReportJson:
    def test_renders_valid_json(self) -> None:
        proj = _make_projection()
        report = build_run_report(proj, [])
        output = render_run_report_json(report)
        parsed = json.loads(output)
        assert parsed["run_id"] == "run-1"
        assert parsed["lifecycle"] == "completed"

    def test_stable_ordering(self) -> None:
        proj = _make_projection()
        report = build_run_report(proj, [])
        out1 = render_run_report_json(report)
        out2 = render_run_report_json(report)
        assert out1 == out2

    def test_no_timestamp_in_rendered_text(self) -> None:
        sig = _make_signal(signal_type=SignalType.VALIDATION_FAILURE)
        proj = _make_projection()
        report = build_run_report(proj, [sig])
        output = render_run_report_json(report)
        assert "created_at" not in output


class TestRenderRunReportMarkdown:
    def test_renders_headline_table(self) -> None:
        proj = _make_projection()
        report = build_run_report(proj, [])
        md = render_run_report_markdown(report)
        assert "# Run Report" in md
        assert "## Headline" in md
        assert "run-1" in md
        assert "completed" in md

    def test_renders_why_stopped_section(self) -> None:
        proj = _make_projection(
            lifecycle=Lifecycle.FAILED,
            outcome=Outcome.FAILED,
        )
        report = build_run_report(proj, [])
        md = render_run_report_markdown(report)
        assert "## Why Stopped" in md
        assert "lifecycle: failed" in md

    def test_renders_native_outcome_and_outcome_reasons(self) -> None:
        sig = _make_signal(
            signal_type=SignalType.BUDGET_EXCEEDED,
            severity=Severity.HIGH,
            subject="budget",
            evidence_refs=[_make_ref("e-budget")],
        )
        proj = _make_projection(lifecycle=Lifecycle.COMPLETED, outcome=Outcome.FAILED)
        report = build_run_report(proj, [sig])
        md = render_run_report_markdown(report)
        assert "| Native Outcome | success |" in md
        assert "## Outcome Reasons" in md
        assert "budget_exceeded" in md
        assert "e-budget" in md

    def test_renders_governance_coverage(self) -> None:
        report = build_run_report(_make_projection(), [])
        md = render_run_report_markdown(report)
        assert "## Governance Coverage" in md
        assert "| authority | unknown |" in md

    def test_renders_scope_outcomes_section(self) -> None:
        sig = _make_signal(signal_type=SignalType.BACKEND_FALLBACK, severity=Severity.MEDIUM)
        sig.scope_ref = "scope-a"
        report = build_run_report(_make_projection(), [sig])
        md = render_run_report_markdown(report)
        assert "## Scope Outcomes" in md
        assert "scope-a" in md
        assert "degraded_success" in md

    def test_renders_none_when_no_scope_outcomes(self) -> None:
        report = build_run_report(_make_projection(), [])
        md = render_run_report_markdown(report)
        assert "## Scope Outcomes" in md
        assert "None." in md

    def test_renders_none_when_no_outcome_reasons(self) -> None:
        proj = _make_projection()
        report = build_run_report(proj, [])
        md = render_run_report_markdown(report)
        assert "## Outcome Reasons" in md

    def test_renders_signal_table_when_signals_present(self) -> None:
        sig = _make_signal(
            signal_type=SignalType.SCOPE_VIOLATION,
            severity=Severity.CRITICAL,
            subject="scope",
            evidence_refs=[_make_ref("e99")],
        )
        proj = _make_projection()
        report = build_run_report(proj, [sig])
        md = render_run_report_markdown(report)
        assert "## Signals" in md
        assert "scope_violation" in md
        assert "critical" in md
        assert "e99" in md

    def test_renders_none_when_no_signals(self) -> None:
        proj = _make_projection()
        report = build_run_report(proj, [])
        md = render_run_report_markdown(report)
        assert "## Signals" in md
        assert "None." in md

    def test_renders_decision_reasons(self) -> None:
        proj = _make_projection(
            decisions=[
                DecisionSummary(
                    domain="gov", decision="block",
                    projected_domain="execution_control",
                ),
            ],
        )
        report = build_run_report(proj, [])
        md = render_run_report_markdown(report)
        assert "## Decision Reasons" in md
        assert "execution_control/block" in md

    def test_renders_evidence_index(self) -> None:
        refs = [_make_ref("evt-10", artifact="run.json")]
        proj = _make_projection(evidence_refs=refs)
        report = build_run_report(proj, [])
        md = render_run_report_markdown(report)
        assert "## Evidence Index" in md
        assert "evt-10" in md
        assert "artifact: run.json" in md

    def test_markdown_is_stable(self) -> None:
        proj = _make_projection()
        report = build_run_report(proj, [])
        md1 = render_run_report_markdown(report)
        md2 = render_run_report_markdown(report)
        assert md1 == md2


class TestSignalSummary:
    def test_roundtrip(self) -> None:
        refs = [_make_ref("e1")]
        ss = SignalSummary(
            signal_id="sig-1",
            type="scope_violation",
            severity="critical",
            subject="scope",
            evidence_refs=refs,
        )
        assert ss.signal_id == "sig-1"
        assert ss.type == "scope_violation"
        assert ss.severity == "critical"
        assert ss.subject == "scope"
        assert len(ss.evidence_refs) == 1


class TestRunReport:
    def test_model_validation_requires_required_fields(self) -> None:
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RunReport()

    def test_timezone_naive_datetime_rejected(self) -> None:
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RunReport(
                run_id="r1",
                lifecycle="completed",
                outcome="success",
                validation="passed",
                scope="clean",
                why_stopped="test",
                started_at=datetime(2024, 1, 1),
            )

    def test_timezone_aware_datetime_accepted(self) -> None:
        report = RunReport(
            run_id="r1",
            lifecycle="completed",
            outcome="success",
            validation="passed",
            scope="clean",
            why_stopped="test",
            started_at=datetime.now(UTC),
        )
        assert report.run_id == "r1"
