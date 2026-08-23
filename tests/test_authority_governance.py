from __future__ import annotations

from datetime import UTC, datetime

from ailuros.core.execution import AuthorityRecord, AuthorityState, Outcome
from ailuros.projection import build_execution_projection
from ailuros.signals import SignalType, derive_signals


def _event(
    event_type: str,
    *,
    event_id: str | None = None,
    timestamp: datetime | None = None,
    payload: dict | None = None,
    step_id: str | None = None,
    scope_ref: str | None = None,
) -> dict:
    ts = timestamp or datetime.now(UTC)
    eid = event_id or f"evt-{event_type}"
    event = {
        "event_id": eid,
        "event_type": event_type,
        "timestamp": ts,
        "payload": payload or {},
        "step_id": step_id,
    }
    if scope_ref is not None:
        event["scope_ref"] = scope_ref
    return event


def _authority_event(
    event_id: str,
    *,
    actor: str = "actor",
    action: str | None = None,
    observed_target: str | None = None,
    requested_target: str | None = None,
    authority_source: str | None = None,
    status: str | None = None,
    required: bool | None = None,
    scope_ref: object | None = None,
) -> dict:
    payload: dict = {"actor": actor}
    if action is not None:
        payload["action"] = action
    if observed_target is not None:
        payload["observed_target"] = observed_target
    if requested_target is not None:
        payload["requested_target"] = requested_target
    if authority_source is not None:
        payload["authority_source"] = authority_source
    if status is not None:
        payload["status"] = status
    if required is not None:
        payload["required"] = required
    if scope_ref is not None:
        payload["scope_ref"] = scope_ref
    return _event("authority_evidence", event_id=event_id, payload=payload)


def _native_success_events() -> list[dict]:
    return [
        _event("run_started", event_id="s"),
        _event("run_completed", event_id="c"),
    ]


# ── Explicit cross-target unauthorized action => authority_violation / FAILED ──


def test_repository_target_mismatch_is_authority_violation() -> None:
    events = _native_success_events() + [
        _authority_event(
            "a",
            actor="agent-1",
            action="write",
            requested_target="repo:project-a",
            observed_target="repo:project-b",
            authority_source="repository_scope",
            status="violation",
        )
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome == Outcome.FAILED
    assert len(proj.authority_records) == 1
    assert proj.authority_records[0].state == AuthorityState.VIOLATION
    assert proj.authority_records[0].requested_target == "repo:project-a"
    assert proj.authority_records[0].observed_target == "repo:project-b"

    signals = derive_signals(proj)
    violation_signals = [s for s in signals if s.type == SignalType.AUTHORITY_VIOLATION]
    assert len(violation_signals) == 1
    assert violation_signals[0].details["observed_target"] == "repo:project-b"


def test_generic_resource_target_mismatch_is_authority_violation() -> None:
    events = _native_success_events() + [
        _authority_event(
            "a",
            actor="agent-1",
            action="invoke",
            requested_target="mcp:resource-a",
            observed_target="mcp:resource-b",
            authority_source="mcp_grant",
            status="denied",
        )
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome == Outcome.FAILED
    assert proj.authority_records[0].state == AuthorityState.VIOLATION


def test_authority_violation_overrides_native_success() -> None:
    events = _native_success_events() + [
        _authority_event("a", actor="agent-1", status="violation")
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome == Outcome.FAILED


def test_authority_violation_with_block_decision_is_still_failed_or_blocked() -> None:
    events = _native_success_events() + [
        _event("governance_decision", event_id="g", payload={"decision": "block"}),
        _authority_event("a", actor="agent-1", status="violation"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome in {Outcome.FAILED, Outcome.BLOCKED}


# ── Missing/insufficient authority evidence => unknown, never allow ────────


def test_required_authority_check_with_unknown_result_is_review_required() -> None:
    events = _native_success_events() + [
        _authority_event("a", actor="agent-1", required=True)
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome == Outcome.REVIEW_REQUIRED
    assert proj.authority_records[0].state == AuthorityState.UNKNOWN

    signals = derive_signals(proj)
    unknown_signals = [s for s in signals if s.type == SignalType.AUTHORITY_UNKNOWN]
    assert len(unknown_signals) == 1


def test_unrequired_unknown_authority_does_not_block() -> None:
    events = _native_success_events() + [_authority_event("a", actor="agent-1")]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome == Outcome.SUCCESS


def test_unknown_authority_is_never_treated_as_allow() -> None:
    events = _native_success_events() + [
        _authority_event("a", actor="agent-1", required=True, status="something_else")
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.authority_records[0].state == AuthorityState.UNKNOWN
    assert proj.outcome != Outcome.FAILED
    assert proj.outcome == Outcome.REVIEW_REQUIRED


# ── Explicit authorization => no violation, no unknown ──────────────────────


def test_explicit_authorized_status_does_not_block() -> None:
    events = _native_success_events() + [
        _authority_event(
            "a",
            actor="agent-1",
            requested_target="repo:project-a",
            observed_target="repo:project-a",
            required=True,
            status="authorized",
        )
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome == Outcome.SUCCESS
    assert proj.authority_records[0].state == AuthorityState.AUTHORIZED
    signals = derive_signals(proj)
    assert not [
        s
        for s in signals
        if s.type in {SignalType.AUTHORITY_VIOLATION, SignalType.AUTHORITY_UNKNOWN}
    ]


# ── Requested vs observed target distinction is preserved ──────────────────


def test_requested_and_observed_target_are_distinct_fields() -> None:
    events = _native_success_events() + [
        _authority_event(
            "a",
            actor="agent-1",
            requested_target="repo:project-a",
            observed_target="repo:project-b",
            status="violation",
        )
    ]
    proj = build_execution_projection("run-1", "test", events)
    record = proj.authority_records[0]
    assert record.requested_target == "repo:project-a"
    assert record.observed_target == "repo:project-b"
    assert record.requested_target != record.observed_target


# ── T1/T2: AuthorityRecord optional scope_ref, projected from explicit evidence ──


def test_authority_record_scope_ref_default_none() -> None:
    record = AuthorityRecord(actor="agent-1", state=AuthorityState.UNKNOWN)
    assert record.scope_ref is None


def test_authority_record_scope_ref_preserved() -> None:
    record = AuthorityRecord(
        actor="agent-1",
        state=AuthorityState.AUTHORIZED,
        scope_ref="scope-a",
    )
    assert record.scope_ref == "scope-a"


def test_authority_record_scope_ref_malformed_rejected() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        AuthorityRecord(
            actor="agent-1",
            state=AuthorityState.UNKNOWN,
            scope_ref=42,
        )


def test_authority_evidence_event_projects_explicit_payload_scope() -> None:
    events = _native_success_events() + [
        _authority_event("a", actor="agent-1", status="authorized", scope_ref="scope-a")
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.authority_records[0].scope_ref == "scope-a"


def test_authority_record_does_not_inherit_run_scope() -> None:
    events = [
        _event("run_started", event_id="s", scope_ref="scope-run-1"),
        _authority_event("a", actor="agent-1", status="authorized"),
        _event("run_completed", event_id="c", scope_ref="scope-run-1"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.scope_ref == "scope-run-1"
    assert proj.authority_records[0].scope_ref is None


def test_authority_record_scope_not_inferred_from_malformed() -> None:
    events = _native_success_events() + [
        _authority_event("a", actor="agent-1", status="authorized", scope_ref=["scope-bad"]),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.authority_records[0].scope_ref is None


# ── T2/T3: record-backed authority signals inherit explicit scope ───────


def test_authority_violation_signal_inherits_record_scope() -> None:
    events = _native_success_events() + [
        _authority_event(
            "a",
            actor="agent-1",
            requested_target="repo:project-a",
            observed_target="repo:project-b",
            status="violation",
            scope_ref="scope-a",
        )
    ]
    proj = build_execution_projection("run-1", "test", events)
    signals = derive_signals(proj)
    violation = [s for s in signals if s.type == SignalType.AUTHORITY_VIOLATION]
    assert len(violation) == 1
    assert violation[0].scope_ref == "scope-a"


def test_authority_violation_signal_unscoped_when_record_unscoped() -> None:
    events = _native_success_events() + [
        _authority_event("a", actor="agent-1", status="violation")
    ]
    proj = build_execution_projection("run-1", "test", events)
    signals = derive_signals(proj)
    violation = [s for s in signals if s.type == SignalType.AUTHORITY_VIOLATION]
    assert len(violation) == 1
    assert violation[0].scope_ref is None


def test_authority_unknown_signal_inherits_record_scope() -> None:
    events = _native_success_events() + [
        _authority_event("a", actor="agent-1", required=True, scope_ref="scope-a")
    ]
    proj = build_execution_projection("run-1", "test", events)
    signals = derive_signals(proj)
    unknown = [s for s in signals if s.type == SignalType.AUTHORITY_UNKNOWN]
    assert len(unknown) == 1
    assert unknown[0].scope_ref == "scope-a"


def test_authority_signals_keep_independent_scope_identity() -> None:
    events = _native_success_events() + [
        _authority_event("a", actor="agent-1", status="violation", scope_ref="scope-a"),
        _authority_event("b", actor="agent-2", status="violation", scope_ref="scope-b"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    signals = derive_signals(proj)
    violation = [s for s in signals if s.type == SignalType.AUTHORITY_VIOLATION]
    assert len(violation) == 2
    assert {s.scope_ref for s in violation} == {"scope-a", "scope-b"}
    assert violation[0].signal_id != violation[1].signal_id
