from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from typer.testing import CliRunner

from ailuros.cli import app
from ailuros.models import Environment, Run, RunStatus, RuntimeEvent, RuntimeEventType
from ailuros.storage import SQLiteStorage


def test_replay_cli_prints_ordered_events(tmp_path):
    db = tmp_path / "runtime.sqlite"
    storage = make_storage(db, "run-1")
    storage.append_event(make_event("evt-1", "run-1", RuntimeEventType.RUN_STARTED))
    storage.append_event(make_event("evt-2", "run-1", RuntimeEventType.GOVERNANCE_DECISION))

    result = CliRunner().invoke(app, ["--db", str(db), "replay", "run-1"])

    assert result.exit_code == 0
    assert "Run: run-1" in result.output
    assert result.output.index("1: run_started") < result.output.index("2: governance_decision")


def test_audit_cli_prints_governance_evidence(tmp_path):
    db = tmp_path / "runtime.sqlite"
    storage = make_storage(db, "run-1")
    storage.append_event(
        make_event(
            "evt-1",
            "run-1",
            RuntimeEventType.TOOL_CALL_REQUESTED,
            {"tool_name": "payment.issue_refund"},
        )
    )
    storage.append_event(
        make_event(
            "evt-2",
            "run-1",
            RuntimeEventType.GOVERNANCE_DECISION,
            {"decision": "require_review", "reason": "refund requires approval"},
        )
    )
    storage.append_event(
        make_event("evt-3", "run-1", RuntimeEventType.PATH_VALIDATION_RESULT, {"valid": True})
    )

    result = CliRunner().invoke(app, ["--db", str(db), "audit", "run-1"])

    assert result.exit_code == 0
    assert "Decision: require_review" in result.output
    assert "Reason: refund requires approval" in result.output
    assert "Tool: payment.issue_refund" in result.output
    assert "Path validation: valid" in result.output


def test_audit_cli_unknown_run_exits_nonzero(tmp_path):
    db = tmp_path / "runtime.sqlite"
    storage = SQLiteStorage(db)
    storage.init()

    result = CliRunner().invoke(app, ["--db", str(db), "audit", "missing-run"])

    assert result.exit_code != 0
    assert "missing-run" in result.output


def test_audit_cli_malformed_payload_exits_nonzero(tmp_path):
    db = tmp_path / "runtime.sqlite"
    storage = make_storage(db, "run-corrupt")
    storage.append_event(
        make_event(
            "evt-1",
            "run-corrupt",
            RuntimeEventType.GOVERNANCE_DECISION,
            {"decision": "allow"},
        )
    )
    with sqlite3.connect(db) as conn:
        conn.execute(
            "UPDATE events SET payload_json = ? WHERE event_id = ?",
            ("{not valid json", "evt-1"),
        )

    result = CliRunner().invoke(app, ["--db", str(db), "audit", "run-corrupt"])

    assert result.exit_code != 0
    assert "corrupt" in result.output.lower() or "run-corrupt" in result.output


def test_replay_cli_malformed_payload_exits_nonzero(tmp_path):
    db = tmp_path / "runtime.sqlite"
    storage = make_storage(db, "run-corrupt")
    storage.append_event(make_event("evt-1", "run-corrupt", RuntimeEventType.RUN_STARTED))
    with sqlite3.connect(db) as conn:
        conn.execute(
            "UPDATE events SET payload_json = ? WHERE event_id = ?",
            ("{not valid json", "evt-1"),
        )

    result = CliRunner().invoke(app, ["--db", str(db), "replay", "run-corrupt"])

    assert result.exit_code != 0
    assert "corrupt" in result.output.lower() or "run-corrupt" in result.output


def make_storage(db, run_id: str) -> SQLiteStorage:
    storage = SQLiteStorage(db)
    storage.init()
    now = datetime.now(UTC)
    storage.create_run(
        Run(
            run_id=run_id,
            agent_id="agent-1",
            environment=Environment.TEST,
            status=RunStatus.RUNNING,
            input={"prompt": "refund"},
            created_at=now,
            updated_at=now,
        )
    )
    return storage


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
