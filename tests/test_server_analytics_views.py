from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from http.server import HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pytest

from ailuros.models import Environment, Run, RunStatus
from ailuros.server import create_app
from ailuros.server.app import _Server
from ailuros.storage import SQLiteStorage


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _dt_iso(dt: datetime) -> str:
    return dt.isoformat()


def _make_run_with_projection(
    storage: SQLiteStorage,
    run_id: str,
    source: str,
    outcome: str | None,
    validation: str | None,
    scope: str | None,
    created_at: datetime,
) -> None:
    run = Run(
        run_id=run_id,
        agent_id="agent",
        environment=Environment.DEVELOPMENT,
        status=RunStatus.COMPLETED,
        input={"prompt": "hi"},
        created_at=created_at,
        updated_at=created_at,
    )
    storage.create_run(run)
    storage.upsert_projection(
        run_id=run_id,
        projection_schema="execution_summary/v1.0",
        projection_version="1.0.0",
        source=source,
        projection_json={
            "run_id": run_id,
            "scope": scope,
        },
        lifecycle_status="completed",
        outcome_summary=outcome,
        validation_summary=validation,
    )


def _make_run(
    storage: SQLiteStorage,
    run_id: str,
    *,
    created_at: datetime | None = None,
) -> Run:
    now = created_at or datetime.now(UTC)
    run = Run(
        run_id=run_id,
        agent_id="agent-1",
        environment=Environment.DEVELOPMENT,
        status=RunStatus.COMPLETED,
        input={"prompt": "task"},
        created_at=now,
        updated_at=now,
    )
    storage.create_run(run)
    return run


def _insert_signal(
    storage: SQLiteStorage,
    run_id: str,
    *,
    signal_id: str | None = None,
    signal_type: str = "validation_failure",
    severity: str = "high",
    subject: str = "validation",
    evidence_refs: list[dict] | None = None,
    details: dict | None = None,
    created_at: datetime | None = None,
) -> dict:
    sid = signal_id or f"sig-{run_id}-{signal_type}"
    created = created_at or datetime.now(UTC)
    signal = {
        "signal_id": sid,
        "run_id": run_id,
        "type": signal_type,
        "severity": severity,
        "subject": subject,
        "evidence_refs": evidence_refs or [],
        "details": details or {},
        "created_at": created.isoformat(),
    }
    existing = storage.get_signals(run_id)
    for s in existing:
        if isinstance(s["created_at"], datetime):
            s["created_at"] = s["created_at"].isoformat()
    existing.append(signal)
    storage.replace_signals(run_id, existing)
    return signal


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


def _get(port: int, path: str) -> tuple[int, dict[str, Any] | list[Any]]:
    resp = urllib.request.urlopen(_url(port, path))
    return resp.status, json.loads(resp.read())


# ── Overview endpoint ──────────────────────────────────────────────────────


class TestOverview:
    def test_empty_window(self, storage, server):
        now = datetime.now(UTC)
        ws = quote(_dt_iso(now - timedelta(hours=1)))
        we = quote(_dt_iso(now))
        status, data = _get(
            server.server_address[1],
            f"/analytics/overview?window_start={ws}&window_end={we}",
        )
        assert status == 200
        assert isinstance(data, dict)
        assert data["total_runs"] == 0
        assert data["outcomes"] == {}
        assert data["validations"] == {}
        assert data["scopes"] == {}
        assert data["source_filter"] is None

    def test_mixed_sources(self, storage, server):
        now = datetime.now(UTC)
        _make_run_with_projection(
            storage, "r-sdk", "sdk", "success", "passed", "clean",
            now - timedelta(minutes=10),
        )
        _make_run_with_projection(
            storage, "r-cli", "cli", "failed", "failed", "violated",
            now - timedelta(minutes=5),
        )
        storage.replace_signals("r-cli", [
            {
                "signal_id": "sig-1",
                "type": "backend_fallback",
                "severity": "medium",
                "subject": "backend",
                "evidence_refs": [],
                "details": {},
                "created_at": now.isoformat(),
            },
        ])

        ws = quote(_dt_iso(now - timedelta(hours=1)))
        we = quote(_dt_iso(now))
        status, data = _get(
            server.server_address[1],
            f"/analytics/overview?window_start={ws}&window_end={we}",
        )
        assert status == 200
        assert data["total_runs"] == 2
        assert data["sources"] == {"sdk": 1, "cli": 1}
        assert data["outcomes"] == {"success": 1, "failed": 1}

    def test_source_filter(self, storage, server):
        now = datetime.now(UTC)
        _make_run_with_projection(
            storage, "r-a", "sdk", "success", "passed", "clean",
            now - timedelta(minutes=10),
        )
        _make_run_with_projection(
            storage, "r-b", "cli", "success", "passed", "clean",
            now - timedelta(minutes=5),
        )

        ws = quote(_dt_iso(now - timedelta(hours=1)))
        we = quote(_dt_iso(now))
        status, data = _get(
            server.server_address[1],
            f"/analytics/overview?window_start={ws}&window_end={we}&source=sdk",
        )
        assert status == 200
        assert data["total_runs"] == 1
        assert data["source_filter"] == "sdk"
        assert data["sources"] == {"sdk": 1}

    def test_missing_window_start_returns_400(self, server):
        now = datetime.now(UTC)
        we = quote(_dt_iso(now))
        port = server.server_address[1]
        with pytest.raises(urllib.error.HTTPError) as exc:
            _get(port, f"/analytics/overview?window_end={we}")
        assert exc.value.code == 400

    def test_missing_window_end_returns_400(self, server):
        now = datetime.now(UTC)
        ws = quote(_dt_iso(now - timedelta(hours=1)))
        port = server.server_address[1]
        with pytest.raises(urllib.error.HTTPError) as exc:
            _get(port, f"/analytics/overview?window_start={ws}")
        assert exc.value.code == 400

    def test_invalid_datetime_returns_400(self, server):
        port = server.server_address[1]
        with pytest.raises(urllib.error.HTTPError) as exc:
            _get(
                port,
                "/analytics/overview?window_start=not-a-date&window_end=2025-01-01T00:00:00Z",
            )
        assert exc.value.code == 400

    def test_naive_datetime_returns_400(self, server):
        port = server.server_address[1]
        with pytest.raises(urllib.error.HTTPError) as exc:
            _get(
                port,
                "/analytics/overview?window_start=2025-01-01T00:00:00"
                "&window_end=2025-06-01T00:00:00",
            )
        assert exc.value.code == 400


# ── Problem list endpoint ──────────────────────────────────────────────────


class TestProblemList:
    def test_empty_no_signals(self, server):
        status, data = _get(server.server_address[1], "/problems")
        assert status == 200
        assert isinstance(data, list)
        assert len(data) == 0

    def test_returns_groups(self, storage, server):
        now = datetime.now(UTC)
        _make_run(storage, "run-a", created_at=now)
        _make_run(storage, "run-b", created_at=now)
        _insert_signal(
            storage, "run-a",
            signal_type="validation_failure", subject="validation",
            severity="high", created_at=now,
        )
        _insert_signal(
            storage, "run-b",
            signal_type="validation_failure", subject="validation",
            severity="high", created_at=now + timedelta(hours=1),
        )
        _insert_signal(
            storage, "run-a",
            signal_type="backend_fallback", subject="backend",
            severity="medium", created_at=now,
        )

        status, data = _get(server.server_address[1], "/problems")
        assert status == 200
        assert len(data) == 2
        vf = data[0]
        assert vf["signal_type"] == "validation_failure"
        assert vf["subject_key"] == "validation"
        assert vf["count"] == 2
        assert set(vf["affected_run_ids"]) == {"run-a", "run-b"}

    def test_source_filter(self, storage, server):
        t1 = datetime(2025, 1, 1, tzinfo=UTC)
        t2 = datetime(2025, 1, 10, tzinfo=UTC)
        t3 = datetime(2025, 1, 20, tzinfo=UTC)

        _make_run(storage, "r1", created_at=t1)
        _make_run(storage, "r2", created_at=t2)
        _make_run(storage, "r3", created_at=t3)
        _insert_signal(
            storage, "r1", signal_type="t", subject="s", created_at=t1,
        )
        _insert_signal(
            storage, "r2", signal_type="t", subject="s", created_at=t2,
        )
        _insert_signal(
            storage, "r3", signal_type="t", subject="s", created_at=t3,
        )

        ws = quote(_dt_iso(datetime(2025, 1, 5, tzinfo=UTC)))
        status, data = _get(
            server.server_address[1],
            f"/problems?window_start={ws}",
        )
        assert status == 200
        assert len(data) == 1
        assert data[0]["count"] == 2

    def test_invalid_datetime_returns_400(self, server):
        port = server.server_address[1]
        with pytest.raises(urllib.error.HTTPError) as exc:
            _get(port, "/problems?window_start=not-valid")
        assert exc.value.code == 400


# ── Problem detail endpoint ────────────────────────────────────────────────


class TestProblemDetail:
    def test_returns_detail(self, storage, server):
        now = datetime.now(UTC)
        _make_run(storage, "r1", created_at=now)
        _make_run(storage, "r2", created_at=now)
        refs = [{"event_id": "evt-1", "artifact": None, "pointer": None}]
        _insert_signal(
            storage, "r1", signal_id="sig-001",
            signal_type="validation_failure", subject="validation",
            evidence_refs=refs, created_at=now,
        )
        _insert_signal(
            storage, "r2", signal_id="sig-002",
            signal_type="validation_failure", subject="validation",
            evidence_refs=[], created_at=now + timedelta(hours=1),
        )

        status, data = _get(
            server.server_address[1],
            "/problems/validation_failure/validation",
        )
        assert status == 200
        assert data["signal_type"] == "validation_failure"
        assert data["subject_key"] == "validation"
        assert data["group"]["count"] == 2
        assert len(data["contributing_signals"]) == 2

    def test_unknown_problem_returns_404(self, server):
        port = server.server_address[1]
        with pytest.raises(urllib.error.HTTPError) as exc:
            _get(port, "/problems/nonexistent_type/nonexistent_subject")
        assert exc.value.code == 404

    def test_with_time_filters(self, storage, server):
        now = datetime.now(UTC)
        _make_run(storage, "r1", created_at=now)
        _insert_signal(
            storage, "r1",
            signal_type="t", subject="s", created_at=now,
        )

        status, data = _get(
            server.server_address[1],
            "/problems/t/s",
        )
        assert status == 200
        assert data["group"]["count"] == 1


# ── Existing routes unaffected ─────────────────────────────────────────────


class TestExistingRoutesUnaffected:
    def test_health_still_works(self, server):
        status, data = _get(server.server_address[1], "/health")
        assert status == 200
        assert data == {"status": "ok"}
