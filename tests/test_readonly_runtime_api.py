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


def _make_run(run_id: str, agent_id: str = "test-agent") -> Run:
    now = datetime.now(UTC)
    return Run(
        run_id=run_id,
        agent_id=agent_id,
        environment=Environment.TEST,
        status=RunStatus.COMPLETED,
        input="test input",
        created_at=now,
        updated_at=now,
    )


def _make_event(
    event_id: str,
    run_id: str,
    event_type: RuntimeEventType,
    sequence: int,
    payload: dict[str, Any] | None = None,
) -> RuntimeEvent:
    return RuntimeEvent(
        event_id=event_id,
        run_id=run_id,
        event_type=event_type,
        timestamp=datetime.now(UTC),
        payload=payload or {},
        sequence=sequence,
    )


def _populate_storage(storage: SQLiteStorage, run_id: str = "run-1") -> None:
    run = _make_run(run_id)
    storage.create_run(run)
    prefix = run_id.replace("-", "_")
    events = [
        _make_event(f"{prefix}_evt_1", run_id, RuntimeEventType.RUN_STARTED, 1),
        _make_event(
            f"{prefix}_evt_2", run_id, RuntimeEventType.TOOL_CALL_REQUESTED, 2,
            {"tool_name": "test-tool"},
        ),
        _make_event(
            f"{prefix}_evt_3", run_id, RuntimeEventType.PATH_VALIDATION_RESULT, 3,
            {"valid": True},
        ),
        _make_event(
            f"{prefix}_evt_4", run_id, RuntimeEventType.GOVERNANCE_DECISION, 4,
            {"decision": "allow", "reason": "all checks passed", "tool_name": "test-tool"},
        ),
        _make_event(f"{prefix}_evt_5", run_id, RuntimeEventType.TOOL_CALL_EXECUTED, 5),
        _make_event(f"{prefix}_evt_6", run_id, RuntimeEventType.RUN_COMPLETED, 6),
    ]
    for event in events:
        storage.append_event(event)


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


class TestHealth:
    def test_ok(self, server):
        status, data = _get(server.server_address[1], "/health")
        assert status == 200
        assert data == {"status": "ok"}


class TestRunDetail:
    def test_returns_run_with_metadata_version(self, storage, server):
        _populate_storage(storage, "run-1")
        status, data = _get(server.server_address[1], "/runs/run-1")
        assert status == 200
        assert data["metadata_version"] == 1
        assert data["run"]["run_id"] == "run-1"
        assert data["run"]["agent_id"] == "test-agent"
        assert data["run"]["environment"] == "test"

    def test_not_found_returns_404(self, server):
        port = server.server_address[1]
        with pytest.raises(urllib.error.HTTPError) as exc:
            _get(port, "/runs/missing-run")
        assert exc.value.code == 404
        body = json.loads(exc.value.read())
        assert "error" in body
        assert "missing-run" in body["error"]

    def test_multiple_runs_independent(self, storage, server):
        _populate_storage(storage, "run-a")
        _populate_storage(storage, "run-b")
        _, data_a = _get(server.server_address[1], "/runs/run-a")
        _, data_b = _get(server.server_address[1], "/runs/run-b")
        assert data_a["run"]["run_id"] == "run-a"
        assert data_b["run"]["run_id"] == "run-b"


class TestRunEvents:
    def test_returns_events_ordered_by_sequence(self, storage, server):
        _populate_storage(storage, "run-1")
        status, data = _get(server.server_address[1], "/runs/run-1/events")
        assert status == 200
        assert data["metadata_version"] == 1
        sequences = [e["sequence"] for e in data["events"]]
        assert sequences == [1, 2, 3, 4, 5, 6]

    def test_not_found_returns_404(self, server):
        port = server.server_address[1]
        with pytest.raises(urllib.error.HTTPError) as exc:
            _get(port, "/runs/missing-run/events")
        assert exc.value.code == 404

    def test_preserves_event_types(self, storage, server):
        _populate_storage(storage, "run-1")
        _, data = _get(server.server_address[1], "/runs/run-1/events")
        types = [e["event_type"] for e in data["events"]]
        assert types == [
            "run_started",
            "tool_call_requested",
            "path_validation_result",
            "governance_decision",
            "tool_call_executed",
            "run_completed",
        ]

    def test_limit(self, storage, server):
        _populate_storage(storage, "run-1")
        status, data = _get(server.server_address[1], "/runs/run-1/events?limit=2")
        assert status == 200
        assert len(data["events"]) == 2

    def test_offset(self, storage, server):
        _populate_storage(storage, "run-1")
        status, data = _get(server.server_address[1], "/runs/run-1/events?offset=3")
        assert status == 200
        assert len(data["events"]) == 3
        assert data["events"][0]["sequence"] == 4

    def test_limit_with_offset(self, storage, server):
        _populate_storage(storage, "run-1")
        status, data = _get(
            server.server_address[1], "/runs/run-1/events?limit=2&offset=2",
        )
        assert status == 200
        assert len(data["events"]) == 2
        assert data["events"][0]["sequence"] == 3

    def test_invalid_limit_returns_400(self, storage, server):
        port = server.server_address[1]
        with pytest.raises(urllib.error.HTTPError) as exc:
            _get(port, "/runs/run-1/events?limit=abc")
        assert exc.value.code == 400

    def test_negative_offset_returns_400(self, storage, server):
        port = server.server_address[1]
        with pytest.raises(urllib.error.HTTPError) as exc:
            _get(port, "/runs/run-1/events?offset=-1")
        assert exc.value.code == 400


class TestNoMutation:
    def test_post_returns_501(self, server):
        port = server.server_address[1]
        req = urllib.request.Request(_url(port, "/runs"), method="POST", data=b"{}")
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req)
        assert exc.value.code == 501

    def test_post_on_detail_returns_501(self, server):
        port = server.server_address[1]
        req = urllib.request.Request(_url(port, "/runs/run-1"), method="POST", data=b"{}")
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req)
        assert exc.value.code == 501

    def test_post_on_events_returns_501(self, server):
        port = server.server_address[1]
        req = urllib.request.Request(_url(port, "/runs/run-1/events"), method="POST", data=b"{}")
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req)
        assert exc.value.code == 501
