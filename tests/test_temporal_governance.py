from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ailuros.projection import build_execution_projection


def _event(
    event_type: str,
    *,
    event_id: str | None = None,
    timestamp: datetime | None = None,
    payload: dict | None = None,
    scope_ref: str | None = None,
) -> dict:
    event: dict = {
        "event_id": event_id or f"evt-{event_type}",
        "event_type": event_type,
        "timestamp": timestamp,
        "payload": payload or {},
    }
    if scope_ref is not None:
        event["scope_ref"] = scope_ref
    return event


# ── T1: temporal attribution from existing evidence only ─────────────────


def test_approval_record_timestamp_attributed_from_own_event() -> None:
    start = datetime(2026, 2, 1, 10, 0, 0, tzinfo=UTC)
    events = [
        _event("run_started", event_id="s", timestamp=start),
        _event(
            "approval_evidence",
            event_id="a",
            timestamp=start + timedelta(seconds=1),
            payload={"subject": "release", "decision": "approved"},
        ),
        _event("run_completed", event_id="c", timestamp=start + timedelta(seconds=2)),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.approval_records[0].timestamp == start + timedelta(seconds=1)


def test_run_lifecycle_timestamps_attributed_from_events() -> None:
    start = datetime(2026, 2, 1, 10, 0, 0, tzinfo=UTC)
    end = start + timedelta(minutes=5)
    events = [
        _event("run_started", event_id="s", timestamp=start),
        _event("run_completed", event_id="c", timestamp=end),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.started_at == start
    assert proj.completed_at == end


def test_approval_record_scope_ref_attributed_from_explicit_evidence() -> None:
    events = [
        _event(
            "approval_evidence",
            event_id="a",
            timestamp=datetime(2026, 2, 1, tzinfo=UTC),
            payload={"subject": "release", "decision": "approved", "scope_ref": "scope-a"},
        ),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.approval_records[0].scope_ref == "scope-a"


def test_missing_timestamp_stays_unknown_not_fabricated() -> None:
    start = datetime(2026, 2, 1, 10, 0, 0, tzinfo=UTC)
    events = [
        _event("run_started", event_id="s", timestamp=start),
        _event("approval_evidence", event_id="a", payload={"subject": "release"}),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.approval_records[0].timestamp is None


# ── T2: later evidence cannot retroactively rewrite earlier attribution ──


def test_later_context_conflict_is_reported_not_last_write_wins() -> None:
    events = [
        _event(
            "governance_context",
            event_id="ctx-1",
            timestamp=datetime(2026, 2, 1, tzinfo=UTC),
            payload={"principal_ref": "principal:alice"},
        ),
        _event(
            "governance_context",
            event_id="ctx-2",
            timestamp=datetime(2026, 2, 2, tzinfo=UTC),
            payload={"principal_ref": "principal:bob"},
        ),
    ]
    proj = build_execution_projection("run-1", "test", events)
    context = proj.governance_context
    assert context is not None
    assert context.principal_ref is None
    assert len(context.inconsistencies) == 1
    assert context.inconsistencies[0].values == ["principal:alice", "principal:bob"]


def test_later_scope_ref_does_not_rewrite_first_run_scope() -> None:
    start = datetime(2026, 2, 1, tzinfo=UTC)
    events = [
        _event("run_started", event_id="s", timestamp=start, scope_ref="scope-a"),
        _event(
            "run_completed",
            event_id="c",
            timestamp=start + timedelta(seconds=1),
            scope_ref="scope-b",
        ),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.scope_ref == "scope-a"


def test_later_approval_does_not_mutate_earlier_record_timestamp() -> None:
    start = datetime(2026, 2, 1, 10, 0, 0, tzinfo=UTC)
    events = [
        _event(
            "approval_evidence",
            event_id="a1",
            timestamp=start,
            payload={"subject": "release", "decision": "approved"},
        ),
        _event(
            "approval_evidence",
            event_id="a2",
            timestamp=start + timedelta(minutes=10),
            payload={"subject": "release", "decision": "denied"},
        ),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert len(proj.approval_records) == 2
    assert proj.approval_records[0].timestamp == start
    assert proj.approval_records[1].timestamp == start + timedelta(minutes=10)


# ── T3: cross-scope attribution stays independent under ordering ─────────


def test_approval_scope_attribution_stays_independent_across_scopes() -> None:
    events = [
        _event(
            "approval_evidence",
            event_id="a1",
            timestamp=datetime(2026, 2, 1, tzinfo=UTC),
            payload={"subject": "release", "decision": "approved", "scope_ref": "scope-a"},
        ),
        _event(
            "approval_evidence",
            event_id="a2",
            timestamp=datetime(2026, 2, 2, tzinfo=UTC),
            payload={"subject": "release", "decision": "denied", "scope_ref": "scope-b"},
        ),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert [r.scope_ref for r in proj.approval_records] == ["scope-a", "scope-b"]


def test_budget_exceeded_in_one_scope_does_not_rewrite_other_scope() -> None:
    events = [
        _event(
            "budget_evidence",
            event_id="b1",
            timestamp=datetime(2026, 2, 1, tzinfo=UTC),
            payload={
                "subject": "budget",
                "unit": "tokens",
                "scope_ref": "scope-a",
                "limit": 100,
                "consumed": 150,
            },
        ),
        _event(
            "budget_evidence",
            event_id="b2",
            timestamp=datetime(2026, 2, 2, tzinfo=UTC),
            payload={
                "subject": "budget",
                "unit": "tokens",
                "scope_ref": "scope-b",
                "limit": 100,
                "consumed": 50,
            },
        ),
    ]
    proj = build_execution_projection("run-1", "test", events)
    by_scope = {r.scope_ref: r for r in proj.budget_records}
    assert by_scope["scope-a"].consumed == 150.0
    assert by_scope["scope-b"].consumed == 50.0
    assert by_scope["scope-a"].scope_ref == "scope-a"
    assert by_scope["scope-b"].scope_ref == "scope-b"


# ── T4: replay determinism ────────────────────────────────────────────────


def test_replay_identical_evidence_yields_identical_projection() -> None:
    start = datetime(2026, 2, 1, 10, 0, 0, tzinfo=UTC)
    events = [
        _event("run_started", event_id="s", timestamp=start),
        _event(
            "approval_evidence",
            event_id="a",
            timestamp=start + timedelta(seconds=1),
            payload={
                "subject": "release",
                "action": "deploy",
                "decision": "approved",
                "scope_ref": "scope-a",
            },
        ),
        _event(
            "governance_context",
            event_id="ctx",
            timestamp=start + timedelta(seconds=2),
            payload={"principal_ref": "principal:alice"},
        ),
        _event("run_completed", event_id="c", timestamp=start + timedelta(seconds=3)),
    ]
    first = build_execution_projection("run-1", "test", events)
    second = build_execution_projection("run-1", "test", events)
    assert first == second
    assert first.approval_records[0].timestamp == second.approval_records[0].timestamp
    assert first.outcome == second.outcome


def test_replay_with_unknown_timestamp_stays_deterministic() -> None:
    start = datetime(2026, 2, 1, 10, 0, 0, tzinfo=UTC)
    events = [
        _event("run_started", event_id="s", timestamp=start),
        _event("approval_evidence", event_id="a", payload={"subject": "release"}),
        _event("run_completed", event_id="c", timestamp=start + timedelta(seconds=1)),
    ]
    first = build_execution_projection("run-1", "test", events)
    second = build_execution_projection("run-1", "test", events)
    assert first == second
    assert first.approval_records[0].timestamp is None
    assert second.approval_records[0].timestamp is None
