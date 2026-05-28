from __future__ import annotations

import json

from typer.testing import CliRunner

from ailuros.cli import app


def test_version_default_text():
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert "0.0.0" in result.output or result.output.strip()


def test_version_json():
    result = CliRunner().invoke(app, ["version", "--output", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["name"] == "ailuros"
    assert isinstance(data["version"], str)


def test_version_json_is_valid_json():
    result = CliRunner().invoke(app, ["version", "--output", "json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert "name" in parsed
    assert "version" in parsed


def test_invalid_output_format_exits_nonzero():
    result = CliRunner().invoke(app, ["version", "--output", "xml"])
    assert result.exit_code != 0


def test_version_default_text_still_works(tmp_path):
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0


def test_run_show_json(tmp_path):
    from ailuros import AilurosRuntime

    db = tmp_path / "runtime.sqlite"
    runtime = AilurosRuntime(storage_path=db)
    run = runtime.start_run("hello")

    result = CliRunner().invoke(
        app, ["--db", str(db), "run", "show", run.run_id, "--output", "json"]
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["run_id"] == run.run_id
    assert "status" in data
    assert "events" in data
    assert isinstance(data["events"], list)


def test_run_show_default_text(tmp_path):
    from ailuros import AilurosRuntime

    db = tmp_path / "runtime.sqlite"
    runtime = AilurosRuntime(storage_path=db)
    run = runtime.start_run("hello")

    result = CliRunner().invoke(app, ["--db", str(db), "run", "show", run.run_id])
    assert result.exit_code == 0
    assert run.run_id in result.output


def test_replay_json(tmp_path):
    from datetime import UTC, datetime

    from ailuros.models import Environment, Run, RunStatus, RuntimeEvent, RuntimeEventType
    from ailuros.storage import SQLiteStorage

    db = tmp_path / "runtime.sqlite"
    storage = SQLiteStorage(db)
    storage.init()
    now = datetime.now(UTC)
    storage.create_run(
        Run(
            run_id="run-replay-json",
            agent_id="agent-1",
            environment=Environment.TEST,
            status=RunStatus.RUNNING,
            input={},
            created_at=now,
            updated_at=now,
        )
    )
    storage.append_event(RuntimeEvent(
        event_id="e1", run_id="run-replay-json",
        event_type=RuntimeEventType.RUN_STARTED, timestamp=now,
    ))

    result = CliRunner().invoke(
        app, ["--db", str(db), "replay", "run-replay-json", "--output", "json"]
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["run_id"] == "run-replay-json"
    assert len(data["events"]) == 1
    assert data["events"][0]["event_id"] == "e1"


def test_audit_json(tmp_path):
    from datetime import UTC, datetime

    from ailuros.models import Environment, Run, RunStatus, RuntimeEvent, RuntimeEventType
    from ailuros.storage import SQLiteStorage

    db = tmp_path / "runtime.sqlite"
    storage = SQLiteStorage(db)
    storage.init()
    now = datetime.now(UTC)
    storage.create_run(
        Run(
            run_id="run-audit-json",
            agent_id="agent-1",
            environment=Environment.TEST,
            status=RunStatus.RUNNING,
            input={},
            created_at=now,
            updated_at=now,
        )
    )
    storage.append_event(
        RuntimeEvent(
            event_id="e1", run_id="run-audit-json",
            event_type=RuntimeEventType.GOVERNANCE_DECISION,
            timestamp=now,
            payload={"decision": "allow", "reason": "ok", "tool_name": "test_tool"},
        )
    )
    storage.append_event(
        RuntimeEvent(
            event_id="e2", run_id="run-audit-json",
            event_type=RuntimeEventType.PATH_VALIDATION_RESULT,
            timestamp=now,
            payload={"valid": True},
        )
    )

    result = CliRunner().invoke(
        app, ["--db", str(db), "audit", "run-audit-json", "--output", "json"]
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["run_id"] == "run-audit-json"
    assert data["decision"] == "allow"
    assert data["reason"] == "ok"


def test_regression_compare_json(tmp_path):
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps({"metadata": {}, "cases": {"a": {"expected_passed": True}}}),
        encoding="utf-8",
    )
    results = tmp_path / "results.json"
    results.write_text(
        json.dumps([{"case_id": "a", "passed": True, "failures": [], "evidence": []}]),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app, ["regression", "compare", str(results), str(baseline), "--output", "json"]
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["passed"] is True
    assert "case_ids_compared" in data
    assert data["regressions"] == []


def test_regression_compare_json_failure(tmp_path):
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps({"metadata": {}, "cases": {"a": {"expected_passed": True}}}),
        encoding="utf-8",
    )
    results = tmp_path / "results.json"
    results.write_text(
        json.dumps([{"case_id": "a", "passed": False, "failures": [], "evidence": []}]),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app, ["regression", "compare", str(results), str(baseline), "--output", "json"]
    )
    assert result.exit_code == 1
    data = json.loads(result.output)
    assert data["passed"] is False
    assert len(data["regressions"]) > 0


def test_eval_json(tmp_path):
    from datetime import UTC, datetime

    from ailuros.models import Environment, Run, RunStatus, RuntimeEvent, RuntimeEventType
    from ailuros.storage import SQLiteStorage

    db = tmp_path / "runtime.sqlite"
    storage = SQLiteStorage(db)
    storage.init()
    now = datetime.now(UTC)
    storage.create_run(
        Run(
            run_id="run-eval-json",
            agent_id="agent-1",
            environment=Environment.TEST,
            status=RunStatus.RUNNING,
            input={},
            created_at=now,
            updated_at=now,
        )
    )

    storage.append_event(RuntimeEvent(
        event_id="e1", run_id="run-eval-json",
        event_type=RuntimeEventType.GOVERNANCE_DECISION, timestamp=now,
        payload={"decision": "block", "allowed": False, "severity": "high"},
    ))
    storage.append_event(RuntimeEvent(
        event_id="e2", run_id="run-eval-json",
        event_type=RuntimeEventType.TOOL_CALL_BLOCKED, timestamp=now,
        payload={"tool_name": "test_tool", "decision": "block"},
    ))

    case_file = tmp_path / "eval_case.json"
    case_file.write_text(json.dumps({
        "id": "test_case",
        "name": "Test",
        "expectations": [{"type": "governance_decision", "allowed": False}],
    }), encoding="utf-8")

    result = CliRunner().invoke(app, [
        "--db", str(db), "eval", "run-eval-json",
        "--case", str(case_file), "--output", "json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["run_id"] == "run-eval-json"
    assert "results" in data
    assert "summary" in data
