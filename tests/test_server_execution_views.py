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

from ailuros.core.execution import (
    EvidenceRef,
    ExecutionProjection,
    Lifecycle,
    Outcome,
    Scope,
    Validation,
)
from ailuros.models import Environment, Run, RunStatus
from ailuros.models.common import Severity
from ailuros.server import create_app
from ailuros.server.app import _Server
from ailuros.signals import GovernanceSignal, SignalType
from ailuros.storage import SQLiteStorage


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


def _make_projection(run_id: str) -> ExecutionProjection:
    now = datetime.now(UTC)
    return ExecutionProjection(
        run_id=run_id,
        source="test",
        schema_version="1.0",
        lifecycle=Lifecycle.COMPLETED,
        outcome=Outcome.SUCCESS,
        validation=Validation.PASSED,
        scope=Scope.CLEAN,
        started_at=now,
        completed_at=now,
        step_count=3,
        decision_count=1,
        event_count=5,
        evidence_refs=[EvidenceRef(event_id="evt_1")],
    )


def _make_signal_dict(
    run_id: str, signal_id: str, signal_type: str = "validation_failure",
) -> dict[str, Any]:
    signal = GovernanceSignal.build(
        run_id=run_id,
        signal_type=SignalType(signal_type),
        severity=Severity.HIGH,
        subject="test",
        details={},
        evidence_refs=[EvidenceRef(event_id="evt_1")],
    )
    return signal.model_dump(mode="json")


def _populate(storage: SQLiteStorage) -> None:
    run = _make_run("run-1")
    storage.create_run(run)

    proj = _make_projection("run-1")
    proj_dict = proj.model_dump(mode="json")
    storage.upsert_projection(
        run_id="run-1",
        projection_schema="execution_summary/v1",
        projection_version="1.0.0",
        source="test",
        projection_json=proj_dict,
        lifecycle_status=proj.lifecycle.value,
        outcome_summary=proj.outcome.value,
        validation_summary=proj.validation.value,
    )

    signal = _make_signal_dict("run-1", "sig-1", "validation_failure")
    storage.replace_signals("run-1", [signal])

    run_no_proj = _make_run("run-no-proj")
    storage.create_run(run_no_proj)


@pytest.fixture
def storage(tmp_path: Path) -> SQLiteStorage:
    db = tmp_path / "test.sqlite"
    s = SQLiteStorage(db)
    s.init()
    _populate(s)
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


class TestRunReport:
    def test_returns_report_for_known_run(self, server):
        status, data = _get(server.server_address[1], "/runs/run-1/report")
        assert status == 200
        assert data["run_id"] == "run-1"
        assert "lifecycle" in data
        assert "outcome" in data
        assert "validation" in data
        assert "scope" in data
        assert "why_stopped" in data

    def test_report_includes_signal_summaries(self, server):
        status, data = _get(server.server_address[1], "/runs/run-1/report")
        assert status == 200
        assert "signal_summaries" in data
        assert len(data["signal_summaries"]) == 1
        sig = data["signal_summaries"][0]
        assert sig["type"] == "validation_failure"
        assert sig["severity"] == "high"
        assert sig["subject"] == "test"
        assert "evidence_refs" in sig

    def test_report_includes_timeline_fields(self, server):
        status, data = _get(server.server_address[1], "/runs/run-1/report")
        assert status == 200
        assert data["step_count"] == 3
        assert data["decision_count"] == 1
        assert data["event_count"] == 5
        assert "started_at" in data

    def test_missing_run_returns_404(self, server):
        port = server.server_address[1]
        with pytest.raises(urllib.error.HTTPError) as exc:
            _get(port, "/runs/nonexistent/report")
        assert exc.value.code == 404

    def test_run_without_projection_returns_404(self, server):
        port = server.server_address[1]
        with pytest.raises(urllib.error.HTTPError) as exc:
            _get(port, "/runs/run-no-proj/report")
        assert exc.value.code == 404

    def test_report_404_has_error_body(self, server):
        port = server.server_address[1]
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(_url(port, "/runs/nonexistent/report"))
        body = json.loads(exc.value.read())
        assert "error" in body


class TestRunSignals:
    def test_returns_signals_for_known_run(self, server):
        status, data = _get(server.server_address[1], "/runs/run-1/signals")
        assert status == 200
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["type"] == "validation_failure"
        assert data[0]["severity"] == "high"
        assert data[0]["subject"] == "test"

    def test_signals_include_evidence_refs(self, server):
        status, data = _get(server.server_address[1], "/runs/run-1/signals")
        assert status == 200
        assert "evidence_refs" in data[0]
        assert len(data[0]["evidence_refs"]) == 1

    def test_run_without_signals_returns_empty_list(self, server):
        status, data = _get(server.server_address[1], "/runs/run-no-proj/signals")
        assert status == 200
        assert data == []

    def test_missing_run_returns_404(self, server):
        port = server.server_address[1]
        with pytest.raises(urllib.error.HTTPError) as exc:
            _get(port, "/runs/nonexistent/signals")
        assert exc.value.code == 404

    def test_signals_404_has_error_body(self, server):
        port = server.server_address[1]
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(_url(port, "/runs/nonexistent/signals"))
        body = json.loads(exc.value.read())
        assert "error" in body


class TestExistingRoutesUnaffected:
    def test_health_still_works(self, server):
        status, data = _get(server.server_address[1], "/health")
        assert status == 200
        assert data == {"status": "ok"}

    def test_list_runs_still_works(self, server):
        status, data = _get(server.server_address[1], "/runs")
        assert status == 200
        assert isinstance(data, list)
        assert len(data) >= 2

    def test_run_detail_still_works(self, server):
        status, data = _get(server.server_address[1], "/runs/run-1")
        assert status == 200
        assert "run" in data
        assert data["run"]["run_id"] == "run-1"
