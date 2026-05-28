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

from ailuros.models import Environment, EvaluationResult, Run, RunStatus
from ailuros.server import create_app
from ailuros.server.app import _Server
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


def _make_evaluation(
    evaluation_id: str,
    run_id: str,
    passed: bool = True,
) -> EvaluationResult:
    return EvaluationResult(
        evaluation_id=evaluation_id,
        run_id=run_id,
        evaluator="test-evaluator",
        passed=passed,
        created_at=datetime.now(UTC),
    )


def _populate(storage: SQLiteStorage) -> None:
    storage.create_run(_make_run("run-pass"))
    storage.create_run(_make_run("run-fail"))
    storage.save_evaluation(_make_evaluation("eval-1", "run-pass", passed=True))
    storage.save_evaluation(_make_evaluation("eval-2", "run-fail", passed=False))


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


class TestEvaluationsList:
    def test_returns_list(self, server):
        status, data = _get(server.server_address[1], "/evaluations")
        assert status == 200
        assert isinstance(data, list)

    def test_includes_summary_fields(self, server):
        status, data = _get(server.server_address[1], "/evaluations")
        assert status == 200
        for item in data:
            assert "run_id" in item
            assert "status" in item
            assert "total_cases" in item
            assert "passed_cases" in item
            assert "failed_cases" in item
            assert "created_at" in item

    def test_no_raw_logs_in_summary(self, server):
        status, data = _get(server.server_address[1], "/evaluations")
        assert status == 200
        for item in data:
            assert "findings" not in item
            assert "metadata" not in item
            assert isinstance(item["total_cases"], int)

    def test_passed_and_failed_status(self, server):
        status, data = _get(server.server_address[1], "/evaluations")
        assert status == 200
        statuses = {item["run_id"]: item["status"] for item in data}
        assert statuses["run-pass"] == "passed"
        assert statuses["run-fail"] == "failed"


class TestEvaluationDetail:
    def test_returns_evaluation_for_known_run(self, server):
        status, data = _get(server.server_address[1], "/evaluations/run-pass")
        assert status == 200
        assert data["run_id"] == "run-pass"
        assert data["passed"] is True

    def test_returns_detailed_result(self, server):
        status, data = _get(server.server_address[1], "/evaluations/run-fail")
        assert status == 200
        assert data["run_id"] == "run-fail"
        assert data["passed"] is False
        assert "evaluation_id" in data
        assert "evaluator" in data
        assert "created_at" in data

    def test_unknown_run_id_returns_404(self, server):
        port = server.server_address[1]
        with pytest.raises(urllib.error.HTTPError) as exc:
            _get(port, "/evaluations/unknown-run")
        assert exc.value.code == 404

    def test_404_has_error_body(self, server):
        port = server.server_address[1]
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(_url(port, "/evaluations/unknown-run"))
        body = json.loads(exc.value.read())
        assert "error" in body
