from __future__ import annotations

from datetime import UTC, datetime

from ailuros.core.execution import Outcome
from ailuros.projection import build_execution_projection


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
    subject: str = "release",
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


def _budget_event(
    event_id: str,
    *,
    subject: str = "budget",
    unit: str = "tokens",
    limit: float | int | None = None,
    consumed: float | int | None = None,
    remaining: float | int | None = None,
    status: str | None = None,
    required: bool | None = None,
) -> dict:
    payload: dict = {"subject": subject, "unit": unit}
    if limit is not None:
        payload["limit"] = limit
    if consumed is not None:
        payload["consumed"] = consumed
    if remaining is not None:
        payload["remaining"] = remaining
    if status is not None:
        payload["status"] = status
    if required is not None:
        payload["required"] = required
    return _event("budget_evidence", event_id=event_id, payload=payload)


def _native_success_events() -> list[dict]:
    return [
        _event("run_started", event_id="s"),
        _event("run_completed", event_id="c"),
    ]


# ── T4 regression matrix: no evidence preserves existing behavior ────────


def test_native_success_without_approval_budget_is_clean() -> None:
    proj = build_execution_projection("run-1", "test", _native_success_events())
    assert proj.outcome == Outcome.SUCCESS


def test_native_failure_without_approval_budget_is_failed() -> None:
    events = [
        _event("run_started", event_id="s"),
        _event("run_failed", event_id="f"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome == Outcome.FAILED


# ── Unresolved required approval => REVIEW_REQUIRED ──────────────────────


def test_native_success_with_unresolved_required_approval_is_review_required() -> None:
    events = _native_success_events() + [
        _approval_event("a", subject="release", required=True)
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome == Outcome.REVIEW_REQUIRED


def test_resolved_required_approval_does_not_force_review() -> None:
    events = _native_success_events() + [
        _approval_event(
            "a", subject="release", action="deploy", required=True, decision="approved"
        )
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome == Outcome.SUCCESS


def test_unresolved_approval_does_not_override_native_failure() -> None:
    events = [
        _event("run_started", event_id="s"),
        _event("run_failed", event_id="f"),
        _approval_event("a", subject="release", required=True),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome == Outcome.FAILED


# ── Explicit budget exceeded => FAILED ───────────────────────────────────


def test_native_success_with_explicit_budget_exceeded_is_failed() -> None:
    events = _native_success_events() + [_budget_event("b", status="exceeded")]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome == Outcome.FAILED


def test_native_success_with_budget_consumed_over_limit_is_failed() -> None:
    events = _native_success_events() + [_budget_event("b", limit=100, consumed=150)]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome == Outcome.FAILED


def test_budget_within_limit_does_not_block() -> None:
    events = _native_success_events() + [_budget_event("b", limit=100, consumed=40)]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome == Outcome.SUCCESS


# ── Required budget evaluation with unknown result => not clean ──────────


def test_native_success_with_unknown_required_budget_is_not_clean() -> None:
    events = _native_success_events() + [_budget_event("b", required=True)]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome != Outcome.SUCCESS
    assert proj.outcome == Outcome.REVIEW_REQUIRED


def test_unknown_budget_not_required_does_not_block() -> None:
    events = _native_success_events() + [_budget_event("b")]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome == Outcome.SUCCESS


# ── Approval denied with observed protected action => FAILED ─────────────


def test_approval_denied_with_observed_action_is_failed() -> None:
    events = _native_success_events() + [
        _approval_event("a", subject="release", action="deploy", decision="denied")
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome == Outcome.FAILED


def test_approval_denied_without_observed_action_is_not_blocking() -> None:
    events = _native_success_events() + [
        _approval_event("a", subject="release", decision="denied")
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome == Outcome.SUCCESS


# ── Existing precedence preserved ────────────────────────────────────────


def test_block_decision_still_blocked() -> None:
    events = _native_success_events() + [
        _event("governance_decision", event_id="g", payload={"decision": "block"})
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome == Outcome.BLOCKED


def test_block_decision_not_lowered_by_unresolved_approval() -> None:
    events = _native_success_events() + [
        _event("governance_decision", event_id="g", payload={"decision": "block"}),
        _approval_event("a", subject="release", required=True),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome == Outcome.BLOCKED


def test_require_review_decision_still_review_required() -> None:
    events = _native_success_events() + [
        _event(
            "governance_decision",
            event_id="g",
            payload={"decision": "require_review"},
        )
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome == Outcome.REVIEW_REQUIRED
