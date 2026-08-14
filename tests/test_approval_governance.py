from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ailuros.core.execution import (
    ApprovalRecord,
    ApprovalState,
    EvidenceRef,
    ExecutionProjection,
    Lifecycle,
    Outcome,
    Scope,
    Validation,
)
from ailuros.projection import build_execution_projection
from ailuros.signals import SignalType, derive_signals


def _event(
    event_type: str,
    *,
    event_id: str | None = None,
    timestamp: datetime | None = None,
    payload: dict | None = None,
    step_id: str | None = None,
) -> dict:
    ts = timestamp or datetime.now(UTC)
    eid = event_id or f"evt-{event_type}"
    return {
        "event_id": eid,
        "event_type": event_type,
        "timestamp": ts,
        "payload": payload or {},
        "step_id": step_id,
    }


def _approval_event(
    event_id: str,
    *,
    subject: str = "subject",
    action: str | None = None,
    required: bool | None = None,
    decision: str | None = None,
    approver_ref: str | None = None,
) -> dict:
    payload: dict = {"subject": subject}
    if action is not None:
        payload["action"] = action
    if required is not None:
        payload["required"] = required
    if decision is not None:
        payload["decision"] = decision
    if approver_ref is not None:
        payload["approver_ref"] = approver_ref
    return _event("approval_evidence", event_id=event_id, payload=payload)


def _record(
    *,
    subject: str = "subject",
    action: str | None = None,
    required: bool | None = None,
    decision: str | None = None,
    state: ApprovalState = ApprovalState.UNKNOWN,
    approver_ref: str | None = None,
    evidence_refs: list[EvidenceRef] | None = None,
) -> ApprovalRecord:
    return ApprovalRecord(
        subject=subject,
        action=action,
        required=required,
        decision=decision,
        state=state,
        approver_ref=approver_ref,
        timestamp=datetime.now(UTC),
        evidence_refs=evidence_refs or [],
    )


def _projection(
    *,
    run_id: str = "run-test",
    approval_records: list[ApprovalRecord] | None = None,
) -> ExecutionProjection:
    now = datetime.now(UTC)
    return ExecutionProjection(
        run_id=run_id,
        source="test",
        schema_version="1.0",
        lifecycle=Lifecycle.COMPLETED,
        outcome=Outcome.SUCCESS,
        validation=Validation.PASSED,
        scope=Scope.CLEAN,
        started_at=now,
        completed_at=now,
        approval_records=approval_records or [],
    )


# ── T1: ApprovalRecord model ────────────────────────────────────────────


def test_approval_state_enum_values() -> None:
    assert ApprovalState.APPROVED.value == "approved"
    assert ApprovalState.DENIED.value == "denied"
    assert ApprovalState.UNKNOWN.value == "unknown"
    assert len(ApprovalState) == 3


def test_approval_record_creation() -> None:
    now = datetime.now(UTC)
    ref = EvidenceRef(event_id="evt-1")
    record = ApprovalRecord(
        subject="release",
        action="deploy",
        required=True,
        decision="approved",
        state=ApprovalState.APPROVED,
        approver_ref="user:alice",
        timestamp=now,
        evidence_refs=[ref],
        source={"event_id": "evt-1"},
    )
    assert record.subject == "release"
    assert record.action == "deploy"
    assert record.required is True
    assert record.decision == "approved"
    assert record.state == ApprovalState.APPROVED
    assert record.approver_ref == "user:alice"
    assert record.timestamp == now
    assert record.evidence_refs == [ref]
    assert record.source == {"event_id": "evt-1"}


def test_approval_record_defaults() -> None:
    record = ApprovalRecord(subject="release", state=ApprovalState.UNKNOWN,
                            timestamp=datetime.now(UTC))
    assert record.action is None
    assert record.required is None
    assert record.decision is None
    assert record.approver_ref is None
    assert record.evidence_refs == []
    assert record.source == {}


def test_approval_record_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        ApprovalRecord(
            subject="release",
            state=ApprovalState.UNKNOWN,
            timestamp=datetime.now(UTC),
            extra_field="bad",
        )


def test_approval_record_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError):
        ApprovalRecord(
            subject="release",
            state=ApprovalState.UNKNOWN,
            timestamp=datetime.now(),
        )


def test_approval_record_serializes_to_json() -> None:
    now = datetime.now(UTC)
    record = ApprovalRecord(
        subject="release",
        action="deploy",
        required=True,
        decision="approved",
        state=ApprovalState.APPROVED,
        approver_ref="user:alice",
        timestamp=now,
        evidence_refs=[EvidenceRef(event_id="evt-1")],
    )
    data = record.model_dump(mode="json")
    assert data["subject"] == "release"
    assert data["action"] == "deploy"
    assert data["required"] is True
    assert data["decision"] == "approved"
    assert data["state"] == "approved"
    assert data["approver_ref"] == "user:alice"
    assert isinstance(data["timestamp"], str)
    assert data["evidence_refs"] == [
        {"event_id": "evt-1", "artifact": None, "pointer": None}
    ]


# ── T2: Project explicit approval evidence ──────────────────────────────


def test_no_approval_events_yields_empty_records() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _event("run_completed", event_id="e2"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.approval_records == []


def test_successful_execution_is_not_proof_of_approval() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _event("run_completed", event_id="e2"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome == Outcome.SUCCESS
    assert proj.approval_records == []


def test_approval_evidence_event_projected() -> None:
    events = [
        _approval_event(
            "e1",
            subject="release",
            action="deploy",
            required=True,
            decision="approved",
            approver_ref="user:alice",
        ),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert len(proj.approval_records) == 1
    record = proj.approval_records[0]
    assert record.subject == "release"
    assert record.action == "deploy"
    assert record.required is True
    assert record.decision == "approved"
    assert record.state == ApprovalState.APPROVED
    assert record.approver_ref == "user:alice"


def test_approval_denied_decision_projected() -> None:
    events = [
        _approval_event("e1", subject="release", decision="rejected"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert len(proj.approval_records) == 1
    assert proj.approval_records[0].state == ApprovalState.DENIED


def test_producer_native_decision_preserved_verbatim() -> None:
    events = [
        _approval_event("e1", subject="release", decision="accepted_by_policy_x"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    record = proj.approval_records[0]
    assert record.decision == "accepted_by_policy_x"
    assert record.state == ApprovalState.UNKNOWN


def test_approval_required_flag_preserved_when_explicit() -> None:
    events = [
        _approval_event("e1", subject="release", required=True),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.approval_records[0].required is True


def test_approval_required_flag_absent_when_not_explicit() -> None:
    events = [
        _approval_event("e1", subject="release"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.approval_records[0].required is None


def test_approval_event_without_subject_is_absent() -> None:
    events = [
        _event(
            "approval_evidence",
            event_id="e1",
            payload={"decision": "approved"},
        ),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.approval_records == []


def test_approval_event_appears_in_evidence_refs() -> None:
    events = [
        _approval_event("e1", subject="release", decision="approved"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    ref_ids = {r.event_id for r in proj.evidence_refs}
    assert "e1" in ref_ids
    record_ref_ids = {r.event_id for r in proj.approval_records[0].evidence_refs}
    assert "e1" in record_ref_ids


# ── T3: Emit narrow approval signals ────────────────────────────────────


def test_approval_required_unresolved_signal() -> None:
    ref = EvidenceRef(event_id="evt-1")
    proj = _projection(
        approval_records=[
            _record(subject="release", required=True, evidence_refs=[ref]),
        ]
    )
    signals = derive_signals(proj)
    unresolved = [s for s in signals if s.type == SignalType.APPROVAL_REQUIRED_UNRESOLVED.value]
    assert len(unresolved) == 1
    assert unresolved[0].subject == "approval"
    assert unresolved[0].evidence_refs == [ref]


def test_no_unresolved_signal_when_approval_resolved() -> None:
    proj = _projection(
        approval_records=[
            _record(
                subject="release",
                required=True,
                decision="approved",
                state=ApprovalState.APPROVED,
            ),
        ]
    )
    signals = derive_signals(proj)
    assert not any(
        s.type == SignalType.APPROVAL_REQUIRED_UNRESOLVED.value for s in signals
    )


@pytest.mark.parametrize(
    "state, decision",
    [
        (ApprovalState.APPROVED, "approved"),
        (ApprovalState.DENIED, "denied"),
    ],
)
def test_resolution_record_suppresses_matching_unresolved_signal(
    state: ApprovalState,
    decision: str,
) -> None:
    proj = _projection(
        approval_records=[
            _record(subject="release", action="deploy", required=True),
            _record(
                subject="release",
                action="deploy",
                decision=decision,
                state=state,
            ),
        ]
    )

    signals = derive_signals(proj)

    assert not any(
        s.type == SignalType.APPROVAL_REQUIRED_UNRESOLVED.value for s in signals
    )


def test_no_unresolved_signal_when_not_required() -> None:
    proj = _projection(
        approval_records=[
            _record(subject="release", required=None),
        ]
    )
    signals = derive_signals(proj)
    assert not any(
        s.type == SignalType.APPROVAL_REQUIRED_UNRESOLVED.value for s in signals
    )


def test_approval_denied_signal() -> None:
    ref = EvidenceRef(event_id="evt-deny")
    proj = _projection(
        approval_records=[
            _record(
                subject="release",
                required=True,
                decision="denied",
                state=ApprovalState.DENIED,
                evidence_refs=[ref],
            ),
        ]
    )
    signals = derive_signals(proj)
    denied = [s for s in signals if s.type == SignalType.APPROVAL_DENIED.value]
    assert len(denied) == 1
    assert denied[0].severity == "high"
    assert denied[0].evidence_refs == [ref]


def test_approval_denied_only_from_explicit_denial() -> None:
    proj = _projection(
        approval_records=[
            _record(subject="release", decision="approved",
                    state=ApprovalState.APPROVED),
            _record(subject="other", decision="unknown",
                    state=ApprovalState.UNKNOWN),
        ]
    )
    signals = derive_signals(proj)
    assert not any(s.type == SignalType.APPROVAL_DENIED.value for s in signals)


def test_clean_projection_yields_no_approval_signals() -> None:
    proj = _projection()
    signals = derive_signals(proj)
    assert signals == []


def test_signal_types_registered() -> None:
    assert SignalType.APPROVAL_REQUIRED_UNRESOLVED.value == "approval_required_unresolved"
    assert SignalType.APPROVAL_DENIED.value == "approval_denied"


# ── T4: Prove no workflow service creep ─────────────────────────────────


def test_no_workflow_service_creep_in_source() -> None:
    import inspect

    import ailuros.core.execution as execution_module
    import ailuros.projection as projection_module
    import ailuros.signals as signals_module

    forbidden = (
        "requests",
        "httpx",
        "urllib",
        "aiohttp",
        "smtplib",
        "celery",
        "kafka",
        "redis",
        "amqp",
        "pika",
        "notification",
        "task_service",
        "human_task",
        "approval_api",
        "approval_service",
        "workflow_service",
        "identity_directory",
        "user_service",
        "enqueue",
        "send_notification",
    )
    for module in (execution_module, projection_module, signals_module):
        source = inspect.getsource(module).lower()
        for token in forbidden:
            assert token not in source, (
                f"{module.__name__} contains forbidden service token {token!r}"
            )


def test_projection_and_signals_are_pure_in_memory() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _approval_event("e2", subject="release", required=True, decision="denied"),
        _event("run_completed", event_id="e3"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    signals = derive_signals(proj)
    assert isinstance(proj.approval_records, list)
    assert isinstance(signals, list)
    assert any(s.type == SignalType.APPROVAL_DENIED.value for s in signals)


def test_reference_producers_share_generic_record_path() -> None:
    events = [
        _approval_event("e1", subject="release", required=True, decision="approved"),
    ]
    everrun = build_execution_projection("run-everrun", "everrun", events)
    clarify = build_execution_projection("run-clarify", "clarify", events)

    assert everrun.approval_records == clarify.approval_records
    assert everrun.source == "everrun"
    assert clarify.source == "clarify"
