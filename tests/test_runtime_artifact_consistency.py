from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ailuros.audit import build_audit_report, build_audit_summary, build_run_summary
from ailuros.models import (
    Environment,
    Run,
    RunStatus,
    RuntimeEvent,
    RuntimeEventType,
)
from ailuros.replay import ReplayService
from ailuros.storage import SQLiteStorage


@pytest.fixture
def storage(tmp_path):
    s = SQLiteStorage(tmp_path / "test.sqlite")
    s.init()
    now = datetime.now(UTC)
    run = Run(
        run_id="art-run-1",
        agent_id="test-agent",
        environment=Environment.TEST,
        status=RunStatus.COMPLETED,
        input="test input",
        created_at=now,
        updated_at=now,
    )
    s.create_run(run)
    s.append_event(RuntimeEvent(
        event_id="evt-1", run_id="art-run-1",
        event_type=RuntimeEventType.RUN_STARTED,
        timestamp=now,
    ))
    s.append_event(RuntimeEvent(
        event_id="evt-2", run_id="art-run-1",
        event_type=RuntimeEventType.USER_INPUT_RECEIVED,
        timestamp=now, payload={"input": "test"},
    ))
    s.append_event(RuntimeEvent(
        event_id="evt-3", run_id="art-run-1",
        event_type=RuntimeEventType.TOOL_CALL_REQUESTED,
        timestamp=now, payload={"tool_name": "read_file", "arguments": {}},
    ))
    s.append_event(RuntimeEvent(
        event_id="evt-4", run_id="art-run-1",
        event_type=RuntimeEventType.GOVERNANCE_DECISION,
        timestamp=now, payload={
            "decision": "allow", "reason": "permitted",
            "tool_name": "read_file",
        },
    ))
    s.append_event(RuntimeEvent(
        event_id="evt-5", run_id="art-run-1",
        event_type=RuntimeEventType.TOOL_CALL_EXECUTED,
        timestamp=now, payload={"tool_name": "read_file"},
    ))
    s.append_event(RuntimeEvent(
        event_id="evt-6", run_id="art-run-1",
        event_type=RuntimeEventType.TOOL_RESULT_RECEIVED,
        timestamp=now, payload={"tool_name": "read_file", "result": "ok"},
    ))
    s.append_event(RuntimeEvent(
        event_id="evt-7", run_id="art-run-1",
        event_type=RuntimeEventType.GOVERNANCE_DECISION,
        timestamp=now, payload={
            "decision": "block", "reason": "not permitted",
            "tool_name": "write_file",
        },
    ))
    s.append_event(RuntimeEvent(
        event_id="evt-8", run_id="art-run-1",
        event_type=RuntimeEventType.RUN_COMPLETED,
        timestamp=now, payload={"status": "completed"},
    ))
    return s


def test_artifact_run_id_consistency(storage):
    run_id = "art-run-1"
    events = storage.list_events(run_id)
    summary = build_run_summary(storage, run_id)
    report = build_audit_report(summary, events)

    for event in events:
        assert event.run_id == run_id
    assert summary.run_id == run_id
    assert report["run_id"] == run_id


def test_artifact_event_count_consistency(storage):
    run_id = "art-run-1"
    events = storage.list_events(run_id)
    summary = build_run_summary(storage, run_id)
    assert summary.event_count == len(events) == 8


def test_artifact_decision_counts_consistency(storage):
    run_id = "art-run-1"
    events = storage.list_events(run_id)
    summary = build_run_summary(storage, run_id)

    expected: dict[str, int] = {}
    for e in events:
        if e.event_type is RuntimeEventType.GOVERNANCE_DECISION:
            d = e.payload.get("decision", "")
            if isinstance(d, str):
                expected[d] = expected.get(d, 0) + 1

    assert summary.decision_counts == {"allow": 1, "block": 1}
    assert summary.decision_counts == expected
    assert summary.blocked_count == expected.get("block", 0)
    assert summary.review_count == expected.get("require_review", 0)


def test_replay_timeline_ordering_is_sequence_based(storage):
    run_id = "art-run-1"
    events = storage.list_events(run_id)
    timeline = ReplayService(storage).build_timeline(run_id)

    assert len(timeline) == len(events)
    for event, entry in zip(events, timeline, strict=True):
        assert entry["sequence_number"] == event.sequence
        assert entry["event_id"] == event.event_id
        assert entry["event_type"] == event.event_type.value


def test_replay_timeline_sequence_increasing(storage):
    run_id = "art-run-1"
    timeline = ReplayService(storage).build_timeline(run_id)
    sequences = [entry["sequence_number"] for entry in timeline]
    assert sequences == sorted(sequences)
    assert sequences == [1, 2, 3, 4, 5, 6, 7, 8]


def test_audit_summary_derived_from_events(storage):
    run_id = "art-run-1"
    events = storage.list_events(run_id)
    audit_summary = build_audit_summary(events)

    assert audit_summary.decision == "block"
    assert audit_summary.reason == "not permitted"
    assert audit_summary.tool == "write_file"
    assert audit_summary.path_validation == "absent"


def test_audit_report_timeline_matches_events(storage):
    run_id = "art-run-1"
    events = storage.list_events(run_id)
    summary = build_run_summary(storage, run_id)
    report = build_audit_report(summary, events)

    report_timeline = report["timeline"]
    assert len(report_timeline) == len(events)

    for event, entry in zip(events, report_timeline, strict=True):
        assert entry["event_id"] == event.event_id
        assert entry["event_type"] == event.event_type.value
        if event.sequence is not None:
            assert entry["sequence"] == event.sequence


def test_audit_report_counts_match_summary(storage):
    run_id = "art-run-1"
    events = storage.list_events(run_id)
    summary = build_run_summary(storage, run_id)
    report = build_audit_report(summary, events)

    counts = report["counts"]
    assert counts["event_count"] == summary.event_count
    assert counts["blocked_count"] == summary.blocked_count
    assert counts["review_count"] == summary.review_count
    assert counts["decision_counts"] == summary.decision_counts
