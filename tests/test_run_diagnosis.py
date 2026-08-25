from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ailuros.core.execution import (
    DecisionSummary,
    EvidenceRef,
    ExecutionProjection,
    GovernanceContext,
    GovernanceContextConflict,
    Lifecycle,
    Outcome,
    Scope,
    Validation,
)
from ailuros.models.common import Severity
from ailuros.run_diagnosis import (
    NextAction,
    RootCause,
    diagnose_run,
    render_diagnosis_json,
    render_diagnosis_markdown,
)
from ailuros.signals import GovernanceSignal, SignalType

FIXED_NOW = datetime(2026, 8, 25, 12, 0, 0, tzinfo=UTC)


def _make_projection(
    *,
    run_id: str = "run-1",
    source: str = "test",
    lifecycle: Lifecycle = Lifecycle.COMPLETED,
    outcome: Outcome = Outcome.SUCCESS,
    validation: Validation = Validation.PASSED,
    scope: Scope = Scope.CLEAN,
    decisions: list[DecisionSummary] | None = None,
    evidence_refs: list[EvidenceRef] | None = None,
    governance_context: GovernanceContext | None = None,
    started_at: datetime = FIXED_NOW,
    completed_at: datetime | None = FIXED_NOW + timedelta(minutes=5),
) -> ExecutionProjection:
    return ExecutionProjection(
        run_id=run_id,
        source=source,
        schema_version="1.0.0",
        lifecycle=lifecycle,
        outcome=outcome,
        validation=validation,
        scope=scope,
        started_at=started_at,
        completed_at=completed_at,
        decisions=decisions or [],
        evidence_refs=evidence_refs or [],
        roles=[],
        governance_context=governance_context,
    )


def _make_ref(event_id: str, artifact: str | None = None) -> EvidenceRef:
    return EvidenceRef(event_id=event_id, artifact=artifact)


def _make_signal(
    *,
    signal_type: SignalType,
    severity: Severity = Severity.HIGH,
    subject: str = "test",
    evidence_refs: list[EvidenceRef] | None = None,
    created_at: datetime = FIXED_NOW,
) -> GovernanceSignal:
    return GovernanceSignal(
        signal_id=f"sig-{signal_type.value}",
        run_id="run-1",
        type=signal_type.value,
        severity=severity.value,
        subject=subject,
        details={},
        evidence_refs=evidence_refs or [],
        rule_version="1.0.0",
        created_at=created_at,
    )


class TestProcessSupervisionNoGuess:
    def test_process_loss_without_vendor_cause_stays_generic(self) -> None:
        proj = _make_projection(
            lifecycle=Lifecycle.FAILED,
            outcome=Outcome.FAILED,
            validation=Validation.NOT_RUN,
        )
        diagnosis = diagnose_run(proj, [])
        assert diagnosis.root_cause == RootCause.EXECUTION_RUNTIME_PROCESS_SUPERVISION
        assert diagnosis.root_cause_detail == "unknown"
        assert diagnosis.incomplete.value == "run_failed"
        assert diagnosis.next_action == NextAction.RETRY

        rendered = render_diagnosis_json(diagnosis).lower()
        assert "volcengine" not in rendered
        assert "oom" not in rendered
        assert "api" not in rendered
        assert "rate limit" not in rendered

    def test_explicit_backend_unavailable_signal_names_sub_cause(self) -> None:
        proj = _make_projection(
            lifecycle=Lifecycle.FAILED,
            outcome=Outcome.FAILED,
        )
        signal = _make_signal(
            signal_type=SignalType.BACKEND_UNAVAILABLE,
            severity=Severity.HIGH,
            subject="backend",
        )
        diagnosis = diagnose_run(proj, [signal])
        assert diagnosis.root_cause == RootCause.EXECUTION_RUNTIME_PROCESS_SUPERVISION
        assert diagnosis.root_cause_detail == "backend_unavailable"

    def test_sub_cause_combined_signals_sorted_deterministically(self) -> None:
        proj = _make_projection(lifecycle=Lifecycle.FAILED, outcome=Outcome.FAILED)
        signals = [
            _make_signal(signal_type=SignalType.BACKEND_FALLBACK, severity=Severity.MEDIUM),
            _make_signal(signal_type=SignalType.CONTEXT_TOO_LARGE, severity=Severity.LOW),
        ]
        diagnosis = diagnose_run(proj, signals)
        assert diagnosis.root_cause_detail == "backend_fallback+context_too_large"


class TestScopeBoundary:
    def test_scope_violation_signal_maps_to_scope_boundary(self) -> None:
        proj = _make_projection()
        signal = _make_signal(
            signal_type=SignalType.SCOPE_VIOLATION,
            severity=Severity.CRITICAL,
            subject="scope",
        )
        diagnosis = diagnose_run(proj, [signal])
        assert diagnosis.root_cause == RootCause.SCOPE_BOUNDARY
        assert diagnosis.next_action == NextAction.REPAIR_PACK_DEFINITION
        assert diagnosis.next_action != NextAction.RETRY
        assert "do not widen scope" in diagnosis.next_action_note

    def test_projection_scope_violated_maps_to_scope_boundary(self) -> None:
        proj = _make_projection(scope=Scope.VIOLATED)
        diagnosis = diagnose_run(proj, [])
        assert diagnosis.root_cause == RootCause.SCOPE_BOUNDARY

    def test_forbidden_path_signal_maps_to_scope_boundary(self) -> None:
        proj = _make_projection()
        signal = _make_signal(
            signal_type=SignalType.FORBIDDEN_PATH_TOUCHED,
            severity=Severity.HIGH,
            subject="path",
        )
        diagnosis = diagnose_run(proj, [signal])
        assert diagnosis.root_cause == RootCause.SCOPE_BOUNDARY


class TestValidation:
    def test_validation_failure_maps_to_validation_and_retry(self) -> None:
        proj = _make_projection(
            lifecycle=Lifecycle.COMPLETED,
            outcome=Outcome.FAILED,
            validation=Validation.FAILED,
        )
        diagnosis = diagnose_run(proj, [])
        assert diagnosis.root_cause == RootCause.VALIDATION
        assert diagnosis.next_action == NextAction.RETRY

    def test_validation_failure_signal_maps_to_validation(self) -> None:
        proj = _make_projection()
        signal = _make_signal(
            signal_type=SignalType.VALIDATION_FAILURE,
            severity=Severity.HIGH,
            subject="validation",
        )
        diagnosis = diagnose_run(proj, [signal])
        assert diagnosis.root_cause == RootCause.VALIDATION

    def test_repeated_validation_failure_maps_to_human_review(self) -> None:
        proj = _make_projection(validation=Validation.FAILED)
        signal = _make_signal(
            signal_type=SignalType.REPEATED_VALIDATION_FAILURE,
            severity=Severity.HIGH,
            subject="repeated_validation",
        )
        diagnosis = diagnose_run(proj, [signal])
        assert diagnosis.root_cause == RootCause.VALIDATION
        assert diagnosis.next_action == NextAction.HUMAN_REVIEW


class TestUnprovenCompletion:
    def test_done_with_missing_validation_is_unproven_not_failed(self) -> None:
        proj = _make_projection(
            lifecycle=Lifecycle.COMPLETED,
            outcome=Outcome.SUCCESS,
            validation=Validation.NOT_RUN,
        )
        diagnosis = diagnose_run(proj, [])
        assert diagnosis.root_cause == RootCause.UNPROVEN_COMPLETION
        assert diagnosis.incomplete.value == "acceptance_unproven"
        assert diagnosis.next_action == NextAction.CONFIRM_RECONCILE
        assert "not a validation failure" in diagnosis.next_action_note

    def test_done_with_unknown_validation_is_unproven(self) -> None:
        proj = _make_projection(
            lifecycle=Lifecycle.COMPLETED,
            outcome=Outcome.SUCCESS,
            validation=Validation.UNKNOWN,
        )
        diagnosis = diagnose_run(proj, [])
        assert diagnosis.root_cause == RootCause.UNPROVEN_COMPLETION

    def test_done_with_failed_validation_is_validation_not_unproven(self) -> None:
        proj = _make_projection(
            lifecycle=Lifecycle.COMPLETED,
            outcome=Outcome.FAILED,
            validation=Validation.FAILED,
        )
        diagnosis = diagnose_run(proj, [])
        assert diagnosis.root_cause == RootCause.VALIDATION
        assert diagnosis.root_cause != RootCause.UNPROVEN_COMPLETION


class TestEvidenceInconsistent:
    def test_contradictory_signal_maps_to_evidence_inconsistent(self) -> None:
        proj = _make_projection()
        signal = _make_signal(
            signal_type=SignalType.EVIDENCE_INCONSISTENCY,
            severity=Severity.MEDIUM,
            subject="evidence",
        )
        diagnosis = diagnose_run(proj, [signal])
        assert diagnosis.root_cause == RootCause.EVIDENCE_INCONSISTENT
        assert diagnosis.next_action == NextAction.HUMAN_REVIEW

    def test_governance_context_inconsistency_maps_to_evidence_inconsistent(self) -> None:
        context = GovernanceContext(
            inconsistencies=[
                GovernanceContextConflict(
                    field="policy_snapshot_ref",
                    values=["snap-a", "snap-b"],
                    source_pointers=["evt-1", "evt-2"],
                )
            ]
        )
        proj = _make_projection(governance_context=context)
        diagnosis = diagnose_run(proj, [])
        assert diagnosis.root_cause == RootCause.EVIDENCE_INCONSISTENT


class TestSourceNeutrality:
    def test_relabeled_source_produces_identical_machine_diagnosis(self) -> None:
        ref = _make_ref("evt-1")
        a = _make_projection(run_id="run-x", source="everrun", evidence_refs=[ref])
        b = _make_projection(run_id="run-x", source="reference-producer", evidence_refs=[ref])
        signals_a = [
            _make_signal(
                signal_type=SignalType.VALIDATION_FAILURE,
                severity=Severity.HIGH,
                subject="validation",
                evidence_refs=[ref],
                created_at=FIXED_NOW,
            )
        ]
        signals_b = [
            _make_signal(
                signal_type=SignalType.VALIDATION_FAILURE,
                severity=Severity.HIGH,
                subject="validation",
                evidence_refs=[ref],
                created_at=FIXED_NOW,
            )
        ]
        out_a = render_diagnosis_json(diagnose_run(a, signals_a))
        out_b = render_diagnosis_json(diagnose_run(b, signals_b))
        assert out_a == out_b
        assert json.loads(out_a)["root_cause"] == "validation"

    def test_machine_diagnosis_is_stable_across_calls(self) -> None:
        proj = _make_projection(
            lifecycle=Lifecycle.FAILED,
            outcome=Outcome.FAILED,
            validation=Validation.NOT_RUN,
        )
        diagnosis = diagnose_run(proj, [])
        assert render_diagnosis_json(diagnosis) == render_diagnosis_json(diagnosis)


class TestCleanAndOtherStates:
    def test_clean_run_has_no_failure(self) -> None:
        proj = _make_projection()
        diagnosis = diagnose_run(proj, [])
        assert diagnosis.incomplete.value == "none"
        assert diagnosis.root_cause == RootCause.UNKNOWN
        assert diagnosis.root_cause_detail == "none"
        assert diagnosis.risk.value == "low"
        assert diagnosis.next_action == NextAction.NONE

    def test_review_required_incomplete(self) -> None:
        proj = _make_projection(outcome=Outcome.REVIEW_REQUIRED)
        diagnosis = diagnose_run(proj, [])
        assert diagnosis.incomplete.value == "blocked_or_review"

    def test_running_lifecycle_is_interrupted_and_inspect(self) -> None:
        proj = _make_projection(
            lifecycle=Lifecycle.RUNNING,
            outcome=Outcome.UNKNOWN,
            completed_at=None,
        )
        diagnosis = diagnose_run(proj, [])
        assert diagnosis.incomplete.value == "run_interrupted"
        assert diagnosis.root_cause == RootCause.UNKNOWN
        assert diagnosis.next_action == NextAction.INSPECT

    def test_approval_denied_is_governed_stop(self) -> None:
        proj = _make_projection(lifecycle=Lifecycle.FAILED, outcome=Outcome.FAILED)
        signal = _make_signal(
            signal_type=SignalType.APPROVAL_DENIED,
            severity=Severity.HIGH,
            subject="approval",
        )
        diagnosis = diagnose_run(proj, [signal])
        assert diagnosis.root_cause == RootCause.UNKNOWN
        assert diagnosis.root_cause_detail == "approval_denied"
        assert diagnosis.next_action == NextAction.HUMAN_REVIEW

    def test_authority_violation_is_governed_stop_with_stop_action(self) -> None:
        proj = _make_projection(lifecycle=Lifecycle.FAILED, outcome=Outcome.FAILED)
        signal = _make_signal(
            signal_type=SignalType.AUTHORITY_VIOLATION,
            severity=Severity.CRITICAL,
            subject="authority",
        )
        diagnosis = diagnose_run(proj, [signal])
        assert diagnosis.root_cause_detail == "authority_violation"
        assert diagnosis.risk.value == "critical"
        assert diagnosis.next_action == NextAction.STOP


class TestEvidenceTrace:
    def test_evidence_refs_collected_and_deduplicated(self) -> None:
        proj = _make_projection(evidence_refs=[_make_ref("e1"), _make_ref("e2")])
        signal = _make_signal(
            signal_type=SignalType.SCOPE_VIOLATION,
            severity=Severity.CRITICAL,
            subject="scope",
            evidence_refs=[_make_ref("e2"), _make_ref("e3")],
        )
        diagnosis = diagnose_run(proj, [signal])
        assert [ref.event_id for ref in diagnosis.evidence_refs] == ["e1", "e2", "e3"]


class TestRenderDiagnosisMarkdown:
    def test_markdown_renders_four_operator_fields(self) -> None:
        proj = _make_projection(
            lifecycle=Lifecycle.FAILED,
            outcome=Outcome.FAILED,
            validation=Validation.NOT_RUN,
        )
        md = render_diagnosis_markdown(diagnose_run(proj, []))
        assert "# Run Diagnosis" in md
        assert "| Incomplete | run_failed |" in md
        assert "| Root Cause | execution_runtime/process_supervision |" in md
        assert "| Risk | high |" in md
        assert "| Next Action | retry |" in md
        assert "## Advisory Note" in md
        assert "## Evidence" in md


class TestDiagnoseCli:
    def test_diagnose_command_json(self, tmp_path: Path) -> None:
        from typer.testing import CliRunner

        from ailuros.cli import app
        from ailuros.models import (
            Environment,
            Run,
            RunStatus,
            RuntimeEvent,
            RuntimeEventType,
        )
        from ailuros.projection import rebuild_projections_and_signals
        from ailuros.storage import SQLiteStorage

        db = tmp_path / "runtime.sqlite"
        storage = SQLiteStorage(db)
        storage.init()
        now = datetime.now(UTC)
        storage.create_run(
            Run(
                run_id="run_cli_diag",
                agent_id="agent",
                environment=Environment.DEVELOPMENT,
                status=RunStatus.RUNNING,
                input={"prompt": "hi"},
                created_at=now,
                updated_at=now,
            )
        )
        storage.append_event(
            RuntimeEvent(
                event_id="evt-start",
                run_id="run_cli_diag",
                event_type=RuntimeEventType.RUN_STARTED,
                timestamp=now,
                payload={},
            )
        )
        storage.append_event(
            RuntimeEvent(
                event_id="evt-fail",
                run_id="run_cli_diag",
                event_type=RuntimeEventType.RUN_FAILED,
                timestamp=now + timedelta(seconds=5),
                payload={},
            )
        )
        rebuild_projections_and_signals(storage, "run_cli_diag")

        result = CliRunner().invoke(
            app,
            ["--db", str(db), "diagnose", "run_cli_diag", "--format", "json"],
        )
        assert result.exit_code == 0, result.output
        parsed = json.loads(result.output)
        assert parsed["run_id"] == "run_cli_diag"
        assert parsed["root_cause"] == "execution_runtime/process_supervision"
        assert parsed["root_cause_detail"] == "unknown"
        assert "volcengine" not in result.output.lower()

    def test_diagnose_command_markdown(self, tmp_path: Path) -> None:
        from typer.testing import CliRunner

        from ailuros.cli import app
        from ailuros.models import (
            Environment,
            Run,
            RunStatus,
            RuntimeEvent,
            RuntimeEventType,
        )
        from ailuros.projection import rebuild_projections_and_signals
        from ailuros.storage import SQLiteStorage

        db = tmp_path / "runtime.sqlite"
        storage = SQLiteStorage(db)
        storage.init()
        now = datetime.now(UTC)
        storage.create_run(
            Run(
                run_id="run_cli_diag_md",
                agent_id="agent",
                environment=Environment.DEVELOPMENT,
                status=RunStatus.RUNNING,
                input={"prompt": "hi"},
                created_at=now,
                updated_at=now,
            )
        )
        storage.append_event(
            RuntimeEvent(
                event_id="evt-start",
                run_id="run_cli_diag_md",
                event_type=RuntimeEventType.RUN_STARTED,
                timestamp=now,
                payload={},
            )
        )
        storage.append_event(
            RuntimeEvent(
                event_id="evt-complete",
                run_id="run_cli_diag_md",
                event_type=RuntimeEventType.RUN_COMPLETED,
                timestamp=now + timedelta(seconds=5),
                payload={},
            )
        )
        rebuild_projections_and_signals(storage, "run_cli_diag_md")

        result = CliRunner().invoke(
            app,
            ["--db", str(db), "diagnose", "run_cli_diag_md", "--format", "md"],
        )
        assert result.exit_code == 0, result.output
        assert "# Run Diagnosis" in result.output
        assert "| Root Cause | unproven_completion |" in result.output
