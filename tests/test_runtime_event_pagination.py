from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from datetime import UTC, datetime
from http.server import HTTPServer
from pathlib import Path
from typing import Any

import pytest

from ailuros.models import Environment, Run, RunStatus, RuntimeEvent, RuntimeEventType
from ailuros.server import create_app
from ailuros.server.app import _Server
from ailuros.storage import SQLiteStorage
from ailuros.storage.sqlite_storage import MAX_EVENT_LIMIT


def _make_run(run_id: str) -> Run:
    now = datetime.now(UTC)
    return Run(
        run_id=run_id,
        agent_id="test-agent",
        environment=Environment.TEST,
        status=RunStatus.COMPLETED,
        input="test input",
        created_at=now,
        updated_at=now,
    )


def _make_event(event_id: str, run_id: str, sequence: int) -> RuntimeEvent:
    return RuntimeEvent(
        event_id=event_id,
        run_id=run_id,
        event_type=RuntimeEventType.RUN_STARTED,
        timestamp=datetime.now(UTC),
        payload={"seq": sequence},
        sequence=sequence,
    )


def _populate_events(storage: SQLiteStorage, run_id: str, count: int) -> None:
    for i in range(count):
        storage.append_event(
            RuntimeEvent(
                event_id=f"{run_id}_evt_{i}",
                run_id=run_id,
                event_type=RuntimeEventType.RUN_STARTED,
                timestamp=datetime.now(UTC),
                payload={"i": i},
            )
        )


def _run_with_events(storage: SQLiteStorage, run_id: str, count: int) -> None:
    storage.create_run(_make_run(run_id))
    _populate_events(storage, run_id, count)


@pytest.fixture
def storage(tmp_path: Path) -> SQLiteStorage:
    db = tmp_path / "test.sqlite"
    s = SQLiteStorage(db)
    s.init()
    return s


@pytest.fixture
def server(storage: SQLiteStorage) -> HTTPServer:
    handler = create_app(storage)
    srv = _Server(("127.0.0.1", 0), handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv


def _url(port: int, path: str) -> str:
    return f"http://127.0.0.1:{port}{path}"


def _get(port: int, path: str) -> tuple[int, dict[str, Any]]:
    resp = urllib.request.urlopen(_url(port, path))
    return resp.status, json.loads(resp.read())


class TestListEventsDefault:
    def test_no_limit_or_offset_returns_all(self, storage: SQLiteStorage) -> None:
        _run_with_events(storage, "run_1", 5)
        events = storage.list_events("run_1")
        assert len(events) == 5

    def test_sequences_are_ordered(self, storage: SQLiteStorage) -> None:
        _run_with_events(storage, "run_1", 5)
        events = storage.list_events("run_1")
        seqs = [e.sequence for e in events]
        assert seqs == [1, 2, 3, 4, 5]

    def test_empty_run_returns_empty_list(self, storage: SQLiteStorage) -> None:
        storage.create_run(_make_run("run_empty"))
        events = storage.list_events("run_empty")
        assert events == []

    def test_empty_page_returns_valid_empty_result(self, storage: SQLiteStorage) -> None:
        _run_with_events(storage, "run_1", 5)
        events = storage.list_events("run_1", offset=10)
        assert events == []


class TestListEventsLimit:
    def test_custom_limit(self, storage: SQLiteStorage) -> None:
        _run_with_events(storage, "run_1", 10)
        events = storage.list_events("run_1", limit=3)
        assert len(events) == 3

    def test_limit_with_offset(self, storage: SQLiteStorage) -> None:
        _run_with_events(storage, "run_1", 10)
        events = storage.list_events("run_1", limit=3, offset=5)
        assert len(events) == 3
        assert events[0].sequence == 6

    def test_limit_exceeding_total(self, storage: SQLiteStorage) -> None:
        _run_with_events(storage, "run_1", 3)
        events = storage.list_events("run_1", limit=100)
        assert len(events) == 3


class TestMaxLimitCap:
    def test_limit_below_cap_is_unchanged(self, storage: SQLiteStorage) -> None:
        _run_with_events(storage, "run_1", 10)
        events = storage.list_events("run_1", limit=MAX_EVENT_LIMIT - 1)
        assert len(events) == 10

    def test_limit_at_cap(self, storage: SQLiteStorage) -> None:
        _run_with_events(storage, "run_1", MAX_EVENT_LIMIT)
        events = storage.list_events("run_1", limit=MAX_EVENT_LIMIT)
        assert len(events) == MAX_EVENT_LIMIT

    def test_limit_exceeding_cap_is_capped(self, storage: SQLiteStorage) -> None:
        _run_with_events(storage, "run_1", MAX_EVENT_LIMIT + 50)
        events = storage.list_events("run_1", limit=MAX_EVENT_LIMIT + 50)
        assert len(events) == MAX_EVENT_LIMIT

    def test_cap_constant_is_positive(self) -> None:
        assert MAX_EVENT_LIMIT > 0
        assert MAX_EVENT_LIMIT == 1000


class TestServerEventEndpoint:
    def test_no_pagination_returns_all(self, storage: SQLiteStorage, server: HTTPServer) -> None:
        _run_with_events(storage, "run-1", 5)
        port = server.server_address[1]
        status, data = _get(port, "/runs/run-1/events")
        assert status == 200
        assert len(data["events"]) == 5

    def test_pagination_metadata(self, storage: SQLiteStorage, server: HTTPServer) -> None:
        _run_with_events(storage, "run-1", 5)
        port = server.server_address[1]
        status, data = _get(port, "/runs/run-1/events?limit=2&offset=1")
        assert status == 200
        assert "pagination" in data
        assert data["pagination"]["limit"] == 2
        assert data["pagination"]["offset"] == 1

    def test_empty_run_returns_empty_page(self, storage: SQLiteStorage, server: HTTPServer) -> None:
        storage.create_run(_make_run("run-empty"))
        port = server.server_address[1]
        status, data = _get(port, "/runs/run-empty/events")
        assert status == 200
        assert data["events"] == []

    def test_offset_beyond_total(self, storage: SQLiteStorage, server: HTTPServer) -> None:
        _run_with_events(storage, "run-1", 5)
        port = server.server_address[1]
        status, data = _get(port, "/runs/run-1/events?offset=10")
        assert status == 200
        assert data["events"] == []

    def test_ordering_by_sequence(self, storage: SQLiteStorage, server: HTTPServer) -> None:
        _run_with_events(storage, "run-1", 6)
        port = server.server_address[1]
        _, data = _get(port, "/runs/run-1/events")
        seqs = [e["sequence"] for e in data["events"]]
        assert seqs == [1, 2, 3, 4, 5, 6]

    def test_not_found_returns_404(self, server: HTTPServer) -> None:
        port = server.server_address[1]
        with pytest.raises(urllib.error.HTTPError) as exc:
            _get(port, "/runs/nonexistent/events")
        assert exc.value.code == 404
