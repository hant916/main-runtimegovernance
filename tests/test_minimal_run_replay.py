from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest

from ailuros.errors import AilurosDataCorruptionError, AilurosNotFoundError
from ailuros.models import Environment, Run, RunStatus, RuntimeEvent, RuntimeEventType
from ailuros.replay import ReplayService
from ailuros.storage import SQLiteStorage


def make_run(run_id: str) -> Run:
    now = datetime.now(UTC)
    return Run(
        run_id=run_id,
        agent_id="agent-1",
        environment=Environment.TEST,
        status=RunStatus.RUNNING,
        input={"prompt": "hello"},
        created_at=now,
        updated_at=now,
    )


def make_event(
    event_id: str,
    run_id: str,
    event_type: RuntimeEventType,
    payload: dict | None = None,
) -> RuntimeEvent:
    return RuntimeEvent(
        event_id=event_id,
        run_id=run_id,
        event_type=event_type,
        timestamp=datetime.now(UTC),
        payload=payload or {},
    )


GOVERNANCE_PAYLOAD = {
    "decision": "allow",
    "allowed": True,
    "reason": "policy check passed",
    "severity": "low",
    "matched_policy_ids": ["pol-1"],
}

TOOL_PAYLOAD = {
    "tool_name": "read_file",
    "arguments": {"path": "/tmp/test.txt"},
}


class TestBuildTimeline:
    def test_reconstructs_timeline_from_ordered_events(self, tmp_path):
        storage = SQLiteStorage(tmp_path / "runtime.sqlite")
        storage.init()
        storage.create_run(make_run("run-1"))
        storage.append_event(make_event("evt-1", "run-1", RuntimeEventType.RUN_STARTED))
        storage.append_event(
            make_event("evt-2", "run-1", RuntimeEventType.TOOL_CALL_REQUESTED, TOOL_PAYLOAD)
        )
        storage.append_event(
            make_event("evt-3", "run-1", RuntimeEventType.GOVERNANCE_DECISION, GOVERNANCE_PAYLOAD)
        )
        storage.append_event(make_event("evt-4", "run-1", RuntimeEventType.RUN_COMPLETED))

        timeline = ReplayService(storage).build_timeline("run-1")

        assert len(timeline) == 4
        assert [entry["sequence_number"] for entry in timeline] == [1, 2, 3, 4]
        assert [entry["event_type"] for entry in timeline] == [
            "run_started",
            "tool_call_requested",
            "governance_decision",
            "run_completed",
        ]

    def test_includes_decision_metadata(self, tmp_path):
        storage = SQLiteStorage(tmp_path / "runtime.sqlite")
        storage.init()
        storage.create_run(make_run("run-1"))
        storage.append_event(
            make_event("evt-1", "run-1", RuntimeEventType.GOVERNANCE_DECISION, GOVERNANCE_PAYLOAD)
        )

        timeline = ReplayService(storage).build_timeline("run-1")

        entry = timeline[0]
        assert entry["metadata"]["decision"] == "allow"
        assert entry["metadata"]["allowed"] is True
        assert entry["metadata"]["reason"] == "policy check passed"
        assert entry["metadata"]["severity"] == "low"
        assert entry["metadata"]["matched_policy_ids"] == ["pol-1"]

    def test_includes_tool_metadata(self, tmp_path):
        storage = SQLiteStorage(tmp_path / "runtime.sqlite")
        storage.init()
        storage.create_run(make_run("run-1"))
        storage.append_event(
            make_event("evt-1", "run-1", RuntimeEventType.TOOL_CALL_REQUESTED, TOOL_PAYLOAD)
        )

        timeline = ReplayService(storage).build_timeline("run-1")

        entry = timeline[0]
        assert entry["metadata"]["tool_name"] == "read_file"
        assert entry["metadata"]["arguments"] == {"path": "/tmp/test.txt"}

    def test_timeline_is_deterministic(self, tmp_path):
        storage = SQLiteStorage(tmp_path / "runtime.sqlite")
        storage.init()
        storage.create_run(make_run("run-1"))
        storage.append_event(make_event("evt-1", "run-1", RuntimeEventType.RUN_STARTED))
        storage.append_event(make_event("evt-2", "run-1", RuntimeEventType.RUN_COMPLETED))

        service = ReplayService(storage)
        first = service.build_timeline("run-1")
        second = service.build_timeline("run-1")

        assert first == second

    def test_timeline_is_read_only(self, tmp_path):
        db_path = tmp_path / "runtime.sqlite"
        storage = SQLiteStorage(db_path)
        storage.init()
        storage.create_run(make_run("run-1"))
        storage.append_event(make_event("evt-1", "run-1", RuntimeEventType.RUN_STARTED))

        before_count = event_count(db_path)
        ReplayService(storage).build_timeline("run-1")
        assert event_count(db_path) == before_count

    def test_unknown_run_fails(self, tmp_path):
        storage = SQLiteStorage(tmp_path / "runtime.sqlite")
        storage.init()

        with pytest.raises(AilurosNotFoundError, match="missing-run"):
            ReplayService(storage).build_timeline("missing-run")

    def test_run_with_no_events_fails(self, tmp_path):
        storage = SQLiteStorage(tmp_path / "runtime.sqlite")
        storage.init()
        storage.create_run(make_run("empty-run"))

        with pytest.raises(AilurosNotFoundError, match="empty-run"):
            ReplayService(storage).build_timeline("empty-run")

    def test_corrupt_payload_fails_visibly(self, tmp_path):
        db_path = tmp_path / "runtime.sqlite"
        storage = SQLiteStorage(db_path)
        storage.init()
        storage.create_run(make_run("run-1"))
        storage.append_event(make_event("evt-1", "run-1", RuntimeEventType.RUN_STARTED))
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "UPDATE events SET payload_json = ? WHERE run_id = ? AND sequence = ?",
                ("{not-json", "run-1", 1),
            )

        with pytest.raises(AilurosDataCorruptionError, match="run-1.*events.payload_json"):
            ReplayService(storage).build_timeline("run-1")

    def test_timeline_includes_event_id_and_timestamp(self, tmp_path):
        storage = SQLiteStorage(tmp_path / "runtime.sqlite")
        storage.init()
        storage.create_run(make_run("run-1"))
        storage.append_event(make_event("evt-abc", "run-1", RuntimeEventType.RUN_STARTED))

        timeline = ReplayService(storage).build_timeline("run-1")

        entry = timeline[0]
        assert entry["event_id"] == "evt-abc"
        assert entry["timestamp"].endswith("+00:00") or entry["timestamp"].endswith("Z")

    def test_no_metadata_for_simple_events(self, tmp_path):
        storage = SQLiteStorage(tmp_path / "runtime.sqlite")
        storage.init()
        storage.create_run(make_run("run-1"))
        storage.append_event(make_event("evt-1", "run-1", RuntimeEventType.RUN_STARTED))

        timeline = ReplayService(storage).build_timeline("run-1")

        assert "metadata" not in timeline[0]


def event_count(db_path) -> int:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) FROM events").fetchone()
    return int(row[0])
