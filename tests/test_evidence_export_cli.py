from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from ailuros import EvidenceRecord
from ailuros.cli import app
from ailuros.evidence.ingest import ingest_evidence
from ailuros.models import Environment, Run, RunStatus
from ailuros.storage import SQLiteStorage


def _make_run(storage: SQLiteStorage, run_id: str) -> Run:
    now = datetime.now(UTC)
    run = Run(
        run_id=run_id,
        agent_id="agent",
        environment=Environment.DEVELOPMENT,
        status=RunStatus.RUNNING,
        input={"prompt": "test"},
        created_at=now,
        updated_at=now,
    )
    storage.create_run(run)
    return run


def _make_record(**kwargs) -> EvidenceRecord:
    base: dict = {
        "version": "1.0.0",
        "run_id": "run-cli-001",
        "event_type": "navigation",
        "payload": {"url": "https://example.com", "title": "Test Page"},
        "timestamp": datetime.now(tz=UTC),
    }
    base.update(kwargs)
    return EvidenceRecord(**base)


class TestEvidenceExportCLI:
    def test_evidence_export_json_default(self, tmp_path: Path) -> None:
        db = tmp_path / "runtime.sqlite"
        storage = SQLiteStorage(db)
        storage.init()
        _make_run(storage, "run-cli-001")
        record = _make_record(run_id="run-cli-001")
        ingest_evidence(storage, record)

        result = CliRunner().invoke(app, ["--db", str(db), "evidence", "run-cli-001"])

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert parsed[0]["event_id"].startswith("evt_")

    def test_evidence_export_json_explicit(self, tmp_path: Path) -> None:
        db = tmp_path / "runtime.sqlite"
        storage = SQLiteStorage(db)
        storage.init()
        _make_run(storage, "run-cli-001")
        record = _make_record(run_id="run-cli-001")
        ingest_evidence(storage, record)

        result = CliRunner().invoke(
            app, ["--db", str(db), "evidence", "run-cli-001", "--output", "json"]
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert len(parsed) == 1

    def test_evidence_export_jsonl(self, tmp_path: Path) -> None:
        db = tmp_path / "runtime.sqlite"
        storage = SQLiteStorage(db)
        storage.init()
        _make_run(storage, "run-cli-001")
        for i in range(3):
            record = _make_record(
                run_id="run-cli-001",
                event_type=f"event_{i}",
                payload={"index": i},
                timestamp=datetime(2025, 1, 15, 10, 30, i, tzinfo=UTC),
            )
            ingest_evidence(storage, record)

        result = CliRunner().invoke(
            app, ["--db", str(db), "evidence", "run-cli-001", "--output", "jsonl"]
        )

        assert result.exit_code == 0
        lines = result.output.splitlines()
        assert len(lines) == 3
        for line in lines:
            parsed = json.loads(line)
            assert parsed["event_id"].startswith("evt_")

    def test_evidence_export_invalid_format_exits_nonzero(self, tmp_path: Path) -> None:
        db = tmp_path / "runtime.sqlite"
        SQLiteStorage(db).init()

        result = CliRunner().invoke(
            app, ["--db", str(db), "evidence", "run-cli-001", "--output", "csv"]
        )

        assert result.exit_code != 0
        assert "csv" in result.output.lower() or "invalid" in result.output.lower()

    def test_evidence_export_missing_run_exits_nonzero(self, tmp_path: Path) -> None:
        db = tmp_path / "runtime.sqlite"
        SQLiteStorage(db).init()

        result = CliRunner().invoke(
            app, ["--db", str(db), "evidence", "nonexistent-run"]
        )

        assert result.exit_code != 0
        assert "nonexistent-run" in result.output or "not found" in result.output.lower()

    def test_evidence_export_is_deterministic(self, tmp_path: Path) -> None:
        db = tmp_path / "runtime.sqlite"
        storage = SQLiteStorage(db)
        storage.init()
        _make_run(storage, "run-cli-001")
        record = _make_record(run_id="run-cli-001")
        ingest_evidence(storage, record)

        result1 = CliRunner().invoke(app, ["--db", str(db), "evidence", "run-cli-001"])
        result2 = CliRunner().invoke(app, ["--db", str(db), "evidence", "run-cli-001"])

        assert result1.exit_code == 0
        assert result2.exit_code == 0
        assert result1.output == result2.output
