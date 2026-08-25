from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from ailuros.core.execution import (
    EvidenceRef,
    ExecutionProjection,
    Lifecycle,
    Outcome,
    Scope,
    Validation,
)
from ailuros.run_diagnosis import (
    IncompleteWork,
    NextAction,
    RootCause,
    RunDiagnosis,
    diagnose_run,
    render_diagnosis_json,
)
from ailuros.run_failure_correlation import (
    RecurrenceState,
    RetrySafety,
    correlate_run_failures,
    failure_signature,
    render_correlation_json,
    render_correlation_markdown,
)

FIXED_NOW = datetime(2026, 8, 25, 12, 0, 0, tzinfo=UTC)


def _make_projection(
    *,
    run_id: str = "run-1",
    source: str = "test",
    lifecycle: Lifecycle = Lifecycle.COMPLETED,
    outcome: Outcome = Outcome.SUCCESS,
    validation: Validation = Validation.PASSED,
    scope: Scope = Scope.CLEAN,
    evidence_refs: list[EvidenceRef] | None = None,
) -> ExecutionProjection:
    return ExecutionProjection(
        run_id=run_id,
        source=source,
        schema_version="1.0.0",
        lifecycle=lifecycle,
        outcome=outcome,
        validation=validation,
        scope=scope,
        started_at=FIXED_NOW,
        completed_at=FIXED_NOW + timedelta(minutes=5),
        decisions=[],
        evidence_refs=evidence_refs or [],
        roles=[],
    )


def _make_ref(event_id: str, artifact: str | None = None) -> EvidenceRef:
    return EvidenceRef(event_id=event_id, artifact=artifact)


def _process_supervision_diagnosis(
    run_id: str,
    *,
    detail: str = "unknown",
    evidence_refs: list[EvidenceRef] | None = None,
) -> RunDiagnosis:
    return RunDiagnosis(
        run_id=run_id,
        incomplete=IncompleteWork.RUN_FAILED,
        root_cause=RootCause.EXECUTION_RUNTIME_PROCESS_SUPERVISION,
        root_cause_detail=detail,
        risk="high",
        next_action=NextAction.RETRY,
        next_action_note="Verify runtime supervision, then retry.",
        evidence_refs=evidence_refs or [],
    )


def _scope_boundary_diagnosis(run_id: str) -> RunDiagnosis:
    return RunDiagnosis(
        run_id=run_id,
        incomplete=IncompleteWork.RUN_FAILED,
        root_cause=RootCause.SCOPE_BOUNDARY,
        root_cause_detail="scope_violation",
        risk="high",
        next_action=NextAction.REPAIR_PACK_DEFINITION,
        next_action_note="Fix the pack scope evidence; do not widen scope.",
        evidence_refs=[],
    )


def _unproven_cause_diagnosis(run_id: str) -> RunDiagnosis:
    return RunDiagnosis(
        run_id=run_id,
        incomplete=IncompleteWork.RUN_FAILED,
        root_cause=RootCause.UNKNOWN,
        root_cause_detail="approval_denied",
        risk="medium",
        next_action=NextAction.HUMAN_REVIEW,
        next_action_note="Respect the denial; route to human review.",
        evidence_refs=[],
    )


class TestFailureSignature:
    def test_signature_uses_closed_structured_fields(self) -> None:
        sig = failure_signature(_process_supervision_diagnosis("run-1"))
        assert sig is not None
        assert sig.root_cause == RootCause.EXECUTION_RUNTIME_PROCESS_SUPERVISION
        assert sig.root_cause_detail == "unknown"

    def test_clean_diagnosis_has_no_signature(self) -> None:
        diagnosis = RunDiagnosis(
            run_id="run-1",
            incomplete=IncompleteWork.NONE,
            root_cause=RootCause.UNKNOWN,
            root_cause_detail="none",
            risk="low",
            next_action=NextAction.NONE,
        )
        assert failure_signature(diagnosis) is None

    def test_unknown_root_cause_has_no_signature(self) -> None:
        assert failure_signature(_unproven_cause_diagnosis("run-1")) is None

    def test_equivalent_diagnoses_yield_identical_signatures(self) -> None:
        a = failure_signature(_process_supervision_diagnosis("run-1"))
        b = failure_signature(_process_supervision_diagnosis("run-2"))
        assert a == b


class TestRecurrenceEscalation:
    def test_two_process_failures_escalate_to_repair_runtime(self) -> None:
        diagnoses = [
            _process_supervision_diagnosis("run-1", evidence_refs=[_make_ref("e1")]),
            _process_supervision_diagnosis("run-2", evidence_refs=[_make_ref("e2")]),
        ]
        correlation = correlate_run_failures(diagnoses)
        assert correlation.recurrence == RecurrenceState.RECURRENT
        assert correlation.retry_safety == RetrySafety.UNSAFE
        assert correlation.recommendation == NextAction.REPAIR_RUNTIME
        assert correlation.recommendation != NextAction.RETRY
        assert correlation.recurrence_count == 2
        assert len(correlation.groups) == 1
        group = correlation.groups[0]
        assert group.count == 2
        assert group.run_ids == ["run-1", "run-2"]
        assert [ref.event_id for ref in group.evidence_refs] == ["e1", "e2"]
        assert "unsafe/ineffective" in correlation.recommendation_note

    def test_single_process_failure_remains_retryable(self) -> None:
        correlation = correlate_run_failures(
            [_process_supervision_diagnosis("run-1")]
        )
        assert correlation.recurrence == RecurrenceState.SINGLE
        assert correlation.retry_safety == RetrySafety.SAFE
        assert correlation.recommendation == NextAction.NONE
        assert correlation.recurrence_count == 1

    def test_process_failure_then_scope_failure_not_repeated(self) -> None:
        diagnoses = [
            _process_supervision_diagnosis("run-1"),
            _scope_boundary_diagnosis("run-2"),
        ]
        correlation = correlate_run_failures(diagnoses)
        assert correlation.recurrence == RecurrenceState.SINGLE
        assert correlation.retry_safety == RetrySafety.SAFE
        assert correlation.recommendation == NextAction.NONE
        assert len(correlation.groups) == 2
        assert all(group.count == 1 for group in correlation.groups)

    def test_different_sub_causes_not_conflated(self) -> None:
        diagnoses = [
            _process_supervision_diagnosis("run-1", detail="unknown"),
            _process_supervision_diagnosis("run-2", detail="backend_unavailable"),
        ]
        correlation = correlate_run_failures(diagnoses)
        assert correlation.recurrence == RecurrenceState.SINGLE
        assert correlation.retry_safety == RetrySafety.SAFE
        assert correlation.recommendation == NextAction.NONE

    def test_multiple_recurrence_groups_kept_separate(self) -> None:
        diagnoses = [
            _process_supervision_diagnosis("run-1"),
            _process_supervision_diagnosis("run-2"),
            _scope_boundary_diagnosis("run-3"),
            _scope_boundary_diagnosis("run-4"),
        ]
        correlation = correlate_run_failures(diagnoses)
        assert correlation.recurrence == RecurrenceState.RECURRENT
        assert correlation.retry_safety == RetrySafety.UNSAFE
        assert correlation.recommendation == NextAction.REPAIR_RUNTIME
        assert len(correlation.groups) == 2
        assert {g.signature.root_cause for g in correlation.groups} == {
            RootCause.EXECUTION_RUNTIME_PROCESS_SUPERVISION,
            RootCause.SCOPE_BOUNDARY,
        }

    def test_non_runtime_recurrence_does_not_escalate(self) -> None:
        diagnoses = [
            _scope_boundary_diagnosis("run-1"),
            _scope_boundary_diagnosis("run-2"),
        ]
        correlation = correlate_run_failures(diagnoses)
        assert correlation.recurrence == RecurrenceState.RECURRENT
        assert correlation.retry_safety == RetrySafety.SAFE
        assert correlation.recommendation == NextAction.NONE


class TestUnprovenAndEmpty:
    def test_failure_without_proven_class_reports_unproven(self) -> None:
        diagnoses = [_unproven_cause_diagnosis("run-1")]
        correlation = correlate_run_failures(diagnoses)
        assert correlation.recurrence == RecurrenceState.UNPROVEN
        assert correlation.retry_safety == RetrySafety.UNPROVEN
        assert correlation.recommendation == NextAction.HUMAN_REVIEW
        assert correlation.unproven_run_ids == ["run-1"]
        assert correlation.groups == []

    def test_unproven_failure_is_not_matched_by_prose(self) -> None:
        diagnoses = [
            _unproven_cause_diagnosis("run-1"),
            _unproven_cause_diagnosis("run-2"),
        ]
        correlation = correlate_run_failures(diagnoses)
        assert correlation.recurrence == RecurrenceState.UNPROVEN
        assert correlation.retry_safety == RetrySafety.UNPROVEN
        assert correlation.recommendation == NextAction.HUMAN_REVIEW
        assert "remediation" in correlation.recommendation_note.lower()

    def test_empty_input_is_none_and_safe(self) -> None:
        correlation = correlate_run_failures([])
        assert correlation.recurrence == RecurrenceState.NONE
        assert correlation.retry_safety == RetrySafety.SAFE
        assert correlation.recommendation == NextAction.NONE
        assert correlation.groups == []
        assert correlation.recurrence_count == 0

    def test_clean_run_only_is_none_and_safe(self) -> None:
        proj = _make_projection()
        correlation = correlate_run_failures([diagnose_run(proj, [])])
        assert correlation.recurrence == RecurrenceState.NONE
        assert correlation.retry_safety == RetrySafety.SAFE


class TestBoundednessAndNeutrality:
    def test_no_accept_and_gates_unchanged(self) -> None:
        diagnoses = [
            _process_supervision_diagnosis("run-1"),
            _process_supervision_diagnosis("run-2"),
        ]
        correlation = correlate_run_failures(diagnoses)
        rendered = render_correlation_json(correlation).lower()
        assert '"accept"' not in rendered
        assert correlation.recommendation in {
            NextAction.NONE,
            NextAction.STOP,
            NextAction.REPAIR_RUNTIME,
            NextAction.HUMAN_REVIEW,
        }

    def test_pure_function_deterministic_across_calls(self) -> None:
        diagnoses = [
            _process_supervision_diagnosis("run-1"),
            _process_supervision_diagnosis("run-2"),
        ]
        a = render_correlation_json(correlate_run_failures(diagnoses))
        b = render_correlation_json(correlate_run_failures(diagnoses))
        assert a == b

    def test_duplicate_run_ids_deduplicated_in_order(self) -> None:
        diagnoses = [
            _process_supervision_diagnosis("run-1"),
            _process_supervision_diagnosis("run-1"),
            _process_supervision_diagnosis("run-2"),
        ]
        correlation = correlate_run_failures(diagnoses)
        assert correlation.run_ids == ["run-1", "run-2"]
        assert correlation.recurrence == RecurrenceState.RECURRENT
        assert correlation.recurrence_count == 2

    def test_source_relabeling_does_not_affect_equality(self) -> None:
        ref_a = _make_ref("evt-1")
        ref_b = _make_ref("evt-2")
        proj_a1 = _make_projection(
            run_id="run-x",
            source="everrun",
            lifecycle=Lifecycle.FAILED,
            outcome=Outcome.FAILED,
            validation=Validation.NOT_RUN,
            evidence_refs=[ref_a],
        )
        proj_a2 = _make_projection(
            run_id="run-y",
            source="everrun",
            lifecycle=Lifecycle.FAILED,
            outcome=Outcome.FAILED,
            validation=Validation.NOT_RUN,
            evidence_refs=[ref_b],
        )
        proj_b1 = _make_projection(
            run_id="run-x",
            source="reference-producer",
            lifecycle=Lifecycle.FAILED,
            outcome=Outcome.FAILED,
            validation=Validation.NOT_RUN,
            evidence_refs=[ref_a],
        )
        proj_b2 = _make_projection(
            run_id="run-y",
            source="reference-producer",
            lifecycle=Lifecycle.FAILED,
            outcome=Outcome.FAILED,
            validation=Validation.NOT_RUN,
            evidence_refs=[ref_b],
        )
        diag_a1 = diagnose_run(proj_a1, [])
        diag_a2 = diagnose_run(proj_a2, [])
        diag_b1 = diagnose_run(proj_b1, [])
        diag_b2 = diagnose_run(proj_b2, [])
        assert render_diagnosis_json(diag_a1) == render_diagnosis_json(diag_b1)
        assert failure_signature(diag_a1) == failure_signature(diag_b1)
        out_a = render_correlation_json(correlate_run_failures([diag_a1, diag_a2]))
        out_b = render_correlation_json(correlate_run_failures([diag_b1, diag_b2]))
        assert out_a == out_b
        parsed = json.loads(out_a)
        assert parsed["retry_safety"] == "unsafe"
        assert parsed["recommendation"] == "repair_runtime"

    def test_evidence_refs_deduplicated_and_sorted(self) -> None:
        diagnoses = [
            _process_supervision_diagnosis(
                "run-1",
                evidence_refs=[_make_ref("b"), _make_ref("a"), _make_ref("b")],
            ),
            _process_supervision_diagnosis(
                "run-2",
                evidence_refs=[_make_ref("c"), _make_ref("a")],
            ),
        ]
        correlation = correlate_run_failures(diagnoses)
        group = correlation.groups[0]
        assert [ref.event_id for ref in group.evidence_refs] == ["a", "b", "c"]


class TestRenderCorrelationMarkdown:
    def test_markdown_shows_n_failures_and_layer(self) -> None:
        diagnoses = [
            _process_supervision_diagnosis("run-1"),
            _process_supervision_diagnosis("run-2"),
        ]
        md = render_correlation_markdown(correlate_run_failures(diagnoses))
        assert "# Run Failure Correlation" in md
        assert "| Recurrence | recurrent |" in md
        assert "| Retry Safety | unsafe |" in md
        assert "| Recommendation | repair_runtime |" in md
        assert "execution_runtime/process_supervision" in md
        assert "| 2 |" in md
        assert "## Advisory Note" in md


class TestCorrelationInputShape:
    def test_accepts_diagnoses_projected_from_real_projections(self) -> None:
        proj_1 = _make_projection(
            run_id="run-a",
            lifecycle=Lifecycle.FAILED,
            outcome=Outcome.FAILED,
            validation=Validation.NOT_RUN,
            evidence_refs=[_make_ref("evt-a")],
        )
        proj_2 = _make_projection(
            run_id="run-b",
            lifecycle=Lifecycle.FAILED,
            outcome=Outcome.FAILED,
            validation=Validation.NOT_RUN,
            evidence_refs=[_make_ref("evt-b")],
        )
        correlation = correlate_run_failures(
            [diagnose_run(proj_1, []), diagnose_run(proj_2, [])]
        )
        assert correlation.recurrence == RecurrenceState.RECURRENT
        assert correlation.retry_safety == RetrySafety.UNSAFE
        assert correlation.recommendation == NextAction.REPAIR_RUNTIME
        assert correlation.run_ids == ["run-a", "run-b"]
