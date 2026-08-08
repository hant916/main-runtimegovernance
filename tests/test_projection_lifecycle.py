from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ailuros.core.execution import Lifecycle, Outcome
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


def test_no_events_yields_unknown_lifecycle() -> None:
    proj = build_execution_projection("run-1", "test", [])
    assert proj.lifecycle == Lifecycle.UNKNOWN
    assert proj.outcome == Outcome.UNKNOWN


def test_run_started_yields_running_lifecycle() -> None:
    events = [_event("run_started")]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.lifecycle == Lifecycle.RUNNING
    assert proj.outcome == Outcome.UNKNOWN


def test_run_completed_yields_success_outcome() -> None:
    ts = datetime.now(UTC)
    events = [
        _event("run_started", timestamp=ts),
        _event("run_completed", timestamp=ts + timedelta(seconds=10)),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.lifecycle == Lifecycle.COMPLETED
    assert proj.outcome == Outcome.SUCCESS


def test_run_failed_yields_failed_outcome() -> None:
    events = [
        _event("run_started"),
        _event("run_failed"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.lifecycle == Lifecycle.FAILED
    assert proj.outcome == Outcome.FAILED


def test_block_decision_yields_blocked_outcome() -> None:
    events = [
        _event("run_started"),
        _event(
            "governance_decision",
            payload={"decision": "block", "tool_name": "bash"},
        ),
        _event("run_completed"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.lifecycle == Lifecycle.COMPLETED
    assert proj.outcome == Outcome.BLOCKED


def test_require_review_decision_yields_review_required_outcome() -> None:
    events = [
        _event("run_started"),
        _event(
            "governance_decision",
            payload={"decision": "require_review", "tool_name": "bash"},
        ),
        _event("run_completed"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome == Outcome.REVIEW_REQUIRED


def test_block_overrides_review_require() -> None:
    events = [
        _event("run_started"),
        _event(
            "governance_decision",
            payload={"decision": "require_review", "tool_name": "bash"},
        ),
        _event(
            "governance_decision",
            payload={"decision": "block", "tool_name": "rm"},
        ),
        _event("run_completed"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome == Outcome.BLOCKED


def test_no_blocking_with_completion_yields_success() -> None:
    events = [
        _event("run_started"),
        _event(
            "governance_decision",
            payload={"decision": "allow", "tool_name": "read"},
        ),
        _event("run_completed"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome == Outcome.SUCCESS


def test_allow_decision_does_not_change_outcome() -> None:
    events = [
        _event("run_started"),
        _event(
            "governance_decision",
            payload={"decision": "warn", "tool_name": "exec"},
        ),
        _event(
            "governance_decision",
            payload={"decision": "sanitize", "tool_name": "write"},
        ),
        _event("run_failed"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome == Outcome.FAILED


def test_started_at_from_run_started() -> None:
    ts = datetime(2025, 1, 1, tzinfo=UTC)
    events = [_event("run_started", timestamp=ts)]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.started_at == ts


def test_completed_at_from_run_completed() -> None:
    started = datetime(2025, 1, 1, tzinfo=UTC)
    completed = datetime(2025, 1, 1, 1, 0, tzinfo=UTC)
    events = [
        _event("run_started", timestamp=started),
        _event("run_completed", timestamp=completed),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.completed_at == completed


def test_completed_at_from_run_failed() -> None:
    started = datetime(2025, 1, 1, tzinfo=UTC)
    failed = datetime(2025, 1, 1, 1, 0, tzinfo=UTC)
    events = [
        _event("run_started", timestamp=started),
        _event("run_failed", timestamp=failed),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.completed_at == failed


def test_does_not_infer_completion_from_last_timestamp() -> None:
    started = datetime(2025, 1, 1, tzinfo=UTC)
    later = datetime(2025, 1, 1, 6, 0, tzinfo=UTC)
    events = [
        _event("run_started", timestamp=started),
        _event("tool_call_executed", timestamp=later),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.lifecycle == Lifecycle.RUNNING
    assert proj.completed_at is None
    assert proj.outcome == Outcome.UNKNOWN


def test_event_count() -> None:
    events = [
        _event("run_started"),
        _event("agent_message"),
        _event("run_completed"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.event_count == 3


def test_decision_count() -> None:
    events = [
        _event("run_started"),
        _event(
            "governance_decision",
            payload={"decision": "allow", "tool_name": "read"},
        ),
        _event(
            "governance_decision",
            payload={"decision": "block", "tool_name": "exec"},
        ),
        _event("run_completed"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.decision_count == 2


def test_step_count_from_unique_step_ids() -> None:
    events = [
        _event("run_started", step_id="step-1"),
        _event("tool_call_executed", step_id="step-1"),
        _event("tool_call_executed", step_id="step-2"),
        _event("run_completed", step_id=None),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.step_count == 2


def test_step_count_zero_when_no_step_ids() -> None:
    events = [
        _event("run_started"),
        _event("run_completed"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.step_count == 0


def test_decision_summary_retains_native_value() -> None:
    events = [
        _event("run_started"),
        _event(
            "governance_decision",
            payload={"decision": "block", "tool_name": "bash"},
        ),
        _event("run_completed"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert len(proj.decisions) == 1
    assert proj.decisions[0].domain == "bash"
    assert proj.decisions[0].decision == "block"


def test_decision_summary_falls_back_to_unknown_domain() -> None:
    events = [
        _event("run_started"),
        _event(
            "governance_decision",
            payload={"decision": "warn"},
        ),
        _event("run_completed"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.decisions[0].domain == "unknown"


def test_evidence_refs_capture_lifecycle_events() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _event("run_completed", event_id="e2"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    ref_ids = [r.event_id for r in proj.evidence_refs]
    assert "e1" in ref_ids
    assert "e2" in ref_ids


def test_evidence_refs_capture_governance_decisions() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _event(
            "governance_decision",
            event_id="e2",
            payload={"decision": "block", "tool_name": "rm"},
        ),
        _event("run_completed", event_id="e3"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    ref_ids = [r.event_id for r in proj.evidence_refs]
    assert "e2" in ref_ids


def test_fallback_started_at_when_no_run_started() -> None:
    events = [_event("agent_message")]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.started_at.tzinfo is not None


def test_mixed_events_without_completion_yields_running() -> None:
    events = [
        _event("run_started", step_id="s1"),
        _event("tool_call_executed", step_id="s1"),
        _event("governance_decision", payload={"decision": "allow", "tool_name": "read"}),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.lifecycle == Lifecycle.RUNNING
    assert proj.outcome == Outcome.UNKNOWN
    assert proj.step_count == 1
    assert proj.decision_count == 1
    assert proj.event_count == 3


def test_schema_version_default() -> None:
    proj = build_execution_projection("run-1", "test", [])
    assert proj.schema_version == "1.0"


def test_schema_version_override() -> None:
    proj = build_execution_projection("run-1", "test", [], schema_version="2.0")
    assert proj.schema_version == "2.0"
