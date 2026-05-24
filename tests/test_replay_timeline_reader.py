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


def make_event(event_id: str, run_id: str, event_type: RuntimeEventType) -> RuntimeEvent:
    return RuntimeEvent(
        event_id=event_id,
        run_id=run_id,
        event_type=event_type,
        timestamp=datetime.now(UTC),
        payload={"event_id": event_id},
    )


def test_replay_returns_stored_timeline_in_sequence_order(tmp_path):
    storage = SQLiteStorage(tmp_path / "runtime.sqlite")
    storage.init()
    storage.create_run(make_run("run-1"))
    storage.append_event(make_event("evt-1", "run-1", RuntimeEventType.RUN_STARTED))
    storage.append_event(make_event("evt-2", "run-1", RuntimeEventType.USER_INPUT_RECEIVED))
    storage.append_event(make_event("evt-3", "run-1", RuntimeEventType.RUN_COMPLETED))

    timeline = ReplayService(storage).load_run("run-1")

    assert [event.sequence for event in timeline] == [1, 2, 3]
    assert [event.event_id for event in timeline] == ["evt-1", "evt-2", "evt-3"]


def test_replay_unknown_run_fails_with_run_id(tmp_path):
    storage = SQLiteStorage(tmp_path / "runtime.sqlite")
    storage.init()

    with pytest.raises(AilurosNotFoundError, match="missing-run"):
        ReplayService(storage).load_run("missing-run")


def test_replay_run_with_no_events_fails_with_run_id(tmp_path):
    storage = SQLiteStorage(tmp_path / "runtime.sqlite")
    storage.init()
    storage.create_run(make_run("empty-run"))

    with pytest.raises(AilurosNotFoundError, match="empty-run"):
        ReplayService(storage).load_run("empty-run")


def test_replay_is_read_only(tmp_path):
    db_path = tmp_path / "runtime.sqlite"
    storage = SQLiteStorage(db_path)
    storage.init()
    storage.create_run(make_run("run-1"))
    storage.append_event(make_event("evt-1", "run-1", RuntimeEventType.RUN_STARTED))
    storage.append_event(make_event("evt-2", "run-1", RuntimeEventType.RUN_COMPLETED))

    before_count = event_count(db_path)
    first = ReplayService(storage).load_run("run-1")
    second = ReplayService(storage).load_run("run-1")

    assert event_count(db_path) == before_count
    assert [event.model_dump() for event in first] == [event.model_dump() for event in second]


def test_replay_corrupt_payload_fails_with_run_id_and_location(tmp_path):
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
        ReplayService(storage).load_run("run-1")


def event_count(db_path) -> int:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) FROM events").fetchone()
    return int(row[0])
