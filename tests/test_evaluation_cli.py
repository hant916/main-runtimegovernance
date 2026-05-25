from __future__ import annotations

import json
from datetime import UTC, datetime

from typer.testing import CliRunner

from ailuros.cli import app
from ailuros.models import Environment, Run, RunStatus
from ailuros.storage import SQLiteStorage
from examples.refund_agent.main import run_demo


def test_eval_cli_passes_refund_golden_case(tmp_path):
    db = tmp_path / "runtime.sqlite"
    run_id, refund_called = run_demo(db)
    case_file = "examples/refund_agent/evaluation/high_refund_requires_review.json"

    result = CliRunner().invoke(app, ["--db", str(db), "eval", run_id, "--case", case_file])

    assert result.exit_code == 0
    assert refund_called is False
    assert "PASS refund.high_value_requires_review.golden" in result.output
    assert "evidence[governance_decision]: seq=" in result.output
    assert "evidence[tool_not_executed]: seq=" in result.output
    assert "Summary: 1 passed, 0 failed" in result.output


def test_eval_cli_exits_nonzero_when_case_fails(tmp_path):
    db = tmp_path / "runtime.sqlite"
    run_id, _ = run_demo(db)
    case_file = tmp_path / "failing_case.json"
    case_file.write_text(
        json.dumps(
            {
                "id": "refund.expected_allow",
                "name": "Wrongly expects allow",
                "expectations": [
                    {
                        "type": "governance_decision",
                        "decision": "allow",
                        "allowed": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["--db", str(db), "eval", run_id, "--case", str(case_file)])

    assert result.exit_code == 1
    assert "FAIL refund.expected_allow" in result.output
    assert "failure[governance_decision]: Expected governance decision" in result.output
    assert "Summary: 0 passed, 1 failed" in result.output


def test_eval_cli_rejects_invalid_case_file(tmp_path):
    db = tmp_path / "runtime.sqlite"
    run_id, _ = run_demo(db)
    case_file = tmp_path / "invalid_case.json"
    case_file.write_text("{not json", encoding="utf-8")

    result = CliRunner().invoke(app, ["--db", str(db), "eval", run_id, "--case", str(case_file)])

    assert result.exit_code == 1
    assert "invalid JSON in evaluation case file" in result.output


def test_eval_cli_missing_run_exits_nonzero(tmp_path):
    db = tmp_path / "runtime.sqlite"
    storage = SQLiteStorage(db)
    storage.init()
    case_file = "examples/refund_agent/evaluation/high_refund_requires_review.json"

    result = CliRunner().invoke(app, ["--db", str(db), "eval", "missing-run", "--case", case_file])

    assert result.exit_code == 1
    assert "missing-run" in result.output


def test_eval_cli_requires_case_file(tmp_path):
    db = tmp_path / "runtime.sqlite"
    storage = SQLiteStorage(db)
    storage.init()
    now = datetime.now(UTC)
    storage.create_run(
        Run(
            run_id="run-1",
            agent_id="agent-1",
            environment=Environment.TEST,
            status=RunStatus.RUNNING,
            created_at=now,
            updated_at=now,
        )
    )

    result = CliRunner().invoke(app, ["--db", str(db), "eval", "run-1"])

    assert result.exit_code == 1
    assert "at least one --case file is required" in result.output
