from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import HTTPServer
from pathlib import Path
from typing import Any

import pytest

from ailuros.audit import build_audit_summary
from ailuros.models import Environment, Run, RunStatus, RuntimeEvent, RuntimeEventType
from ailuros.server import create_app
from ailuros.server.app import _Server
from ailuros.storage import SQLiteStorage


def _make_run(run_id: str, agent_id: str = "test-agent") -> Run:
    now = datetime.now(timezone.utc)  # noqa: UP017
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
        timestamp=datetime.now(timezone.utc),  # noqa: UP017
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


class TestListRuns:
    def test_empty(self, server):
        status, data = _get(server.server_address[1], "/runs")
        assert status == 200
        assert data == []

    def test_with_data(self, storage, server):
        _populate_storage(storage, "run-a")
        _populate_storage(storage, "run-b")
        status, data = _get(server.server_address[1], "/runs")
        assert status == 200
        run_ids = [r["run_id"] for r in data]
        assert run_ids == ["run-b", "run-a"]


class TestReplay:
    def test_not_found_returns_404(self, server):
        port = server.server_address[1]
        with pytest.raises(urllib.error.HTTPError) as exc:
            _get(port, "/runs/missing/replay")
        assert exc.value.code == 404

    def test_preserves_event_order(self, storage, server):
        _populate_storage(storage, "run-1")
        status, data = _get(server.server_address[1], "/runs/run-1/replay")
        assert status == 200
        sequences = [e["sequence"] for e in data]
        assert sequences == [1, 2, 3, 4, 5, 6]

    def test_event_types_preserved(self, storage, server):
        _populate_storage(storage, "run-1")
        _, data = _get(server.server_address[1], "/runs/run-1/replay")
        types = [e["event_type"] for e in data]
        assert types == [
            "run_started",
            "tool_call_requested",
            "path_validation_result",
            "governance_decision",
            "tool_call_executed",
            "run_completed",
        ]


class TestAudit:
    def test_not_found_returns_404(self, server):
        port = server.server_address[1]
        with pytest.raises(urllib.error.HTTPError) as exc:
            _get(port, "/runs/missing/audit")
        assert exc.value.code == 404

    def test_matches_service_semantics(self, storage, server):
        _populate_storage(storage, "run-1")
        _, data = _get(server.server_address[1], "/runs/run-1/audit")
        events = storage.list_events("run-1")
        summary = build_audit_summary(events)
        assert data == {
            "decision": summary.decision,
            "reason": summary.reason,
            "tool": summary.tool,
            "path_validation": summary.path_validation,
        }


class TestNoMutation:
    def test_post_returns_501(self, server):
        port = server.server_address[1]
        req = urllib.request.Request(_url(port, "/runs"), method="POST", data=b"{}")
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req)
        assert exc.value.code == 501


class TestUnknownPath:
    def test_returns_404(self, server):
        port = server.server_address[1]
        with pytest.raises(urllib.error.HTTPError) as exc:
            _get(port, "/unknown")
        assert exc.value.code == 404


class TestServerDefaultHost:
    def test_default_is_localhost(self):
        from inspect import signature

        from ailuros.server import run_server

        sig = signature(run_server)
        default = sig.parameters["host"].default
        assert default == "127.0.0.1"
