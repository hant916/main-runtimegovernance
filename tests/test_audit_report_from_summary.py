from __future__ import annotations

from datetime import UTC, datetime

from ailuros.audit import RunSummary, build_audit_report
from ailuros.models import RuntimeEvent, RuntimeEventType


def make_event(
    event_id: str,
    event_type: RuntimeEventType,
    sequence: int | None = None,
) -> RuntimeEvent:
    return RuntimeEvent(
        event_id=event_id,
        run_id="run-1",
        event_type=event_type,
        timestamp=datetime.now(UTC),
        sequence=sequence,
    )


def test_audit_report_contract_fields():
    events = [
        make_event("evt-1", RuntimeEventType.RUN_STARTED, sequence=1),
        make_event("evt-2", RuntimeEventType.USER_INPUT_RECEIVED, sequence=2),
        make_event("evt-3", RuntimeEventType.GOVERNANCE_DECISION, sequence=3),
        make_event("evt-4", RuntimeEventType.RUN_COMPLETED, sequence=4),
    ]
    summary = RunSummary(
        run_id="run-1",
        status="completed",
        event_count=4,
        decision_counts={"allow": 1},
        blocked_count=0,
        review_count=0,
        started_at=events[0].timestamp.isoformat(),
        completed_at=events[3].timestamp.isoformat(),
    )

    report = build_audit_report(summary, events)

    assert report["metadata_version"] == "1"
    assert report["run_id"] == "run-1"
    assert report["status"] == "completed"
    assert report["counts"]["event_count"] == 4
    assert report["counts"]["decision_counts"] == {"allow": 1}
    assert report["counts"]["blocked_count"] == 0
    assert report["counts"]["review_count"] == 0
    assert len(report["timeline"]) == 4


def test_audit_report_timeline_matches_events():
    events = [
        make_event("evt-a", RuntimeEventType.RUN_STARTED, sequence=1),
        make_event("evt-b", RuntimeEventType.GOVERNANCE_DECISION, sequence=2),
        make_event("evt-c", RuntimeEventType.TOOL_CALL_EXECUTED, sequence=3),
    ]
    summary = RunSummary(
        run_id="run-2",
        status="running",
        event_count=3,
        decision_counts={},
        blocked_count=0,
        review_count=0,
    )

    report = build_audit_report(summary, events)

    assert report["run_id"] == "run-2"
    assert report["status"] == "running"
    assert len(report["timeline"]) == 3
    for i, entry in enumerate(report["timeline"]):
        assert entry["event_id"] == events[i].event_id
        assert entry["event_type"] == events[i].event_type.value
        assert entry["sequence"] == events[i].sequence


def test_audit_report_timeline_omits_sequence_when_none():
    events = [
        RuntimeEvent(
            event_id="evt-1",
            run_id="run-3",
            event_type=RuntimeEventType.RUN_STARTED,
            timestamp=datetime.now(UTC),
            sequence=None,
        )
    ]
    summary = RunSummary(
        run_id="run-3",
        status="started",
        event_count=1,
        decision_counts={},
        blocked_count=0,
        review_count=0,
    )

    report = build_audit_report(summary, events)

    assert "sequence" not in report["timeline"][0]


def test_audit_report_counts_reflect_decisions():
    events = [
        make_event("evt-1", RuntimeEventType.RUN_STARTED, sequence=1),
        make_event("evt-2", RuntimeEventType.GOVERNANCE_DECISION, sequence=2),
        make_event("evt-3", RuntimeEventType.GOVERNANCE_DECISION, sequence=3),
        make_event("evt-4", RuntimeEventType.GOVERNANCE_DECISION, sequence=4),
    ]
    summary = RunSummary(
        run_id="run-4",
        status="completed",
        event_count=4,
        decision_counts={"allow": 1, "block": 1, "require_review": 1},
        blocked_count=1,
        review_count=1,
    )

    report = build_audit_report(summary, events)

    assert report["counts"]["decision_counts"] == {"allow": 1, "block": 1, "require_review": 1}
    assert report["counts"]["blocked_count"] == 1
    assert report["counts"]["review_count"] == 1
