from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from typer.testing import CliRunner

from ailuros.cli import app
from ailuros.models import (
    Environment,
    Run,
    RunStatus,
    RuntimeEvent,
    RuntimeEventType,
)
from ailuros.projection import rebuild_projections_and_signals
from ailuros.storage import SQLiteStorage


def _make_run(storage: SQLiteStorage, run_id: str) -> None:
    now = datetime.now(UTC)
    run = Run(
        run_id=run_id,
        agent_id="agent",
        environment=Environment.DEVELOPMENT,
        status=RunStatus.RUNNING,
        input={"prompt": "hi"},
        created_at=now,
        updated_at=now,
    )
    storage.create_run(run)


def _make_event(
    run_id: str,
    event_type: RuntimeEventType,
    *,
    event_id: str | None = None,
    timestamp: datetime | None = None,
    payload: dict | None = None,
    step_id: str | None = None,
) -> RuntimeEvent:
    ts = timestamp or datetime.now(UTC)
    eid = event_id or f"evt-{event_type.value}"
    return RuntimeEvent(
        event_id=eid,
        run_id=run_id,
        step_id=step_id,
        event_type=event_type,
        timestamp=ts,
        payload=payload or {},
    )


class TestReportCliJson:
    def test_json_format_returns_valid_report(self, tmp_path: Path) -> None:
        db = tmp_path / "runtime.sqlite"
        storage = SQLiteStorage(db)
        storage.init()
        _make_run(storage, "run_json")

        now = datetime.now(UTC)
        storage.append_event(
            _make_event("run_json", RuntimeEventType.RUN_STARTED, timestamp=now)
        )
        storage.append_event(
            _make_event(
                "run_json",
                RuntimeEventType.RUN_COMPLETED,
                timestamp=now + timedelta(seconds=5),
            )
        )

        rebuild_projections_and_signals(storage, "run_json")

        result = CliRunner().invoke(
            app, ["--db", str(db), "report", "run_json", "--format", "json"]
        )

        assert result.exit_code == 0, result.output
        parsed = json.loads(result.output)
        assert parsed["run_id"] == "run_json"
        assert parsed["lifecycle"] == "completed"
        assert parsed["outcome"] == "success"
        assert "why_stopped" in parsed
        assert "signal_summaries" in parsed
        assert "decision_reasons" in parsed

    def test_json_format_output_stable(self, tmp_path: Path) -> None:
        db = tmp_path / "runtime.sqlite"
        storage = SQLiteStorage(db)
        storage.init()
        _make_run(storage, "run_stable")

        now = datetime.now(UTC)
        storage.append_event(
            _make_event("run_stable", RuntimeEventType.RUN_STARTED, timestamp=now)
        )
        storage.append_event(
            _make_event(
                "run_stable",
                RuntimeEventType.GOVERNANCE_DECISION,
                timestamp=now + timedelta(seconds=1),
                payload={"decision": "allow", "tool_name": "read"},
            )
        )
        storage.append_event(
            _make_event(
                "run_stable",
                RuntimeEventType.RUN_COMPLETED,
                timestamp=now + timedelta(seconds=5),
            )
        )

        rebuild_projections_and_signals(storage, "run_stable")

        out1 = CliRunner().invoke(
            app, ["--db", str(db), "report", "run_stable", "--format", "json"]
        )
        out2 = CliRunner().invoke(
            app, ["--db", str(db), "report", "run_stable", "--format", "json"]
        )

        assert out1.exit_code == 0
        assert out2.exit_code == 0
        assert out1.output == out2.output


class TestReportCliMarkdown:
    def test_markdown_format_renders_expected_sections(self, tmp_path: Path) -> None:
        db = tmp_path / "runtime.sqlite"
        storage = SQLiteStorage(db)
        storage.init()
        _make_run(storage, "run_md")

        now = datetime.now(UTC)
        storage.append_event(
            _make_event("run_md", RuntimeEventType.RUN_STARTED, timestamp=now)
        )
        storage.append_event(
            _make_event(
                "run_md",
                RuntimeEventType.RUN_COMPLETED,
                timestamp=now + timedelta(seconds=5),
            )
        )

        rebuild_projections_and_signals(storage, "run_md")

        result = CliRunner().invoke(
            app, ["--db", str(db), "report", "run_md", "--format", "md"]
        )

        assert result.exit_code == 0, result.output
        assert "# Run Report" in result.output
        assert "## Headline" in result.output
        assert "## Why Stopped" in result.output
        assert "## Timeline" in result.output
        assert "## Decision Reasons" in result.output
        assert "## Signals" in result.output
        assert "## Changes" in result.output
        assert "## Roles" in result.output
        assert "## Evidence Index" in result.output

    def test_markdown_output_stable(self, tmp_path: Path) -> None:
        db = tmp_path / "runtime.sqlite"
        storage = SQLiteStorage(db)
        storage.init()
        _make_run(storage, "run_md_stable")

        now = datetime.now(UTC)
        storage.append_event(
            _make_event("run_md_stable", RuntimeEventType.RUN_STARTED, timestamp=now)
        )
        storage.append_event(
            _make_event(
                "run_md_stable",
                RuntimeEventType.RUN_COMPLETED,
                timestamp=now + timedelta(seconds=5),
            )
        )

        rebuild_projections_and_signals(storage, "run_md_stable")

        out1 = CliRunner().invoke(
            app, ["--db", str(db), "report", "run_md_stable", "--format", "md"]
        )
        out2 = CliRunner().invoke(
            app, ["--db", str(db), "report", "run_md_stable", "--format", "md"]
        )

        assert out1.exit_code == 0
        assert out2.exit_code == 0
        assert out1.output == out2.output


class TestReportCliUnknownRun:
    def test_unknown_run_exits_nonzero(self, tmp_path: Path) -> None:
        db = tmp_path / "runtime.sqlite"
        storage = SQLiteStorage(db)
        storage.init()

        result = CliRunner().invoke(
            app, ["--db", str(db), "report", "run_missing", "--format", "json"]
        )

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "run_missing" in result.output


class TestReportCliProjectionUnavailable:
    def test_no_projection_exits_nonzero_with_guidance(self, tmp_path: Path) -> None:
        db = tmp_path / "runtime.sqlite"
        storage = SQLiteStorage(db)
        storage.init()
        _make_run(storage, "run_no_proj")

        result = CliRunner().invoke(
            app, ["--db", str(db), "report", "run_no_proj", "--format", "json"]
        )

        assert result.exit_code != 0
        assert "No projection found" in result.output or "--rebuild" in result.output

    def test_rebuild_flag_succeeds_with_run_events(self, tmp_path: Path) -> None:
        db = tmp_path / "runtime.sqlite"
        storage = SQLiteStorage(db)
        storage.init()
        _make_run(storage, "run_rebuild_test")

        now = datetime.now(UTC)
        storage.append_event(
            _make_event(
                "run_rebuild_test", RuntimeEventType.RUN_STARTED, timestamp=now
            )
        )
        storage.append_event(
            _make_event(
                "run_rebuild_test",
                RuntimeEventType.RUN_COMPLETED,
                timestamp=now + timedelta(seconds=5),
            )
        )

        result = CliRunner().invoke(
            app,
            ["--db", str(db), "report", "run_rebuild_test", "--format", "json", "--rebuild"],
        )

        assert result.exit_code == 0, result.output
        parsed = json.loads(result.output)
        assert parsed["run_id"] == "run_rebuild_test"
        assert parsed["lifecycle"] == "completed"

    def test_refuses_silent_derived_state_when_no_flag(self, tmp_path: Path) -> None:
        db = tmp_path / "runtime.sqlite"
        storage = SQLiteStorage(db)
        storage.init()
        _make_run(storage, "run_no_flag")

        now = datetime.now(UTC)
        storage.append_event(
            _make_event("run_no_flag", RuntimeEventType.RUN_STARTED, timestamp=now)
        )

        result = CliRunner().invoke(
            app, ["--db", str(db), "report", "run_no_flag", "--format", "json"]
        )

        assert result.exit_code != 0
        assert "No projection" in result.output or "--rebuild" in result.output
