from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from typer.testing import CliRunner

from ailuros.cli import app
from ailuros.core.execution import (
    ExecutionProjection,
    Lifecycle,
    Outcome,
    Scope,
    Validation,
)
from ailuros.models import Environment, Run, RunStatus
from ailuros.storage import SQLiteStorage

HERE = Path(__file__).resolve().parent
SECOND_PRODUCER = HERE.parent / "fixtures" / "runtime-evidence" / "second-producer"
INVALID_DUPLICATE = SECOND_PRODUCER / "invalid" / "duplicate-event-id"

FIXED_NOW = datetime(2026, 8, 25, 12, 0, 0, tzinfo=UTC)


def _make_storage_with_failed_runs(db_path: Path, run_ids: list[str]) -> None:
    """Seed a storage with runs whose projections diagnose as failed runs.

    Each projection is a terminal FAILED run with unrun validation, which
    ``diagnose_run`` classifies as an execution_runtime/process_supervision
    failure. Signals are intentionally empty so grouping relies only on the
    structured RootCause plus its structured detail, never on prose.
    """
    storage = SQLiteStorage(db_path)
    storage.init()
    for run_id in run_ids:
        storage.create_run(
            Run(
                run_id=run_id,
                agent_id="agent",
                environment=Environment.DEVELOPMENT,
                status=RunStatus.FAILED,
                input={"prompt": "hi"},
                created_at=FIXED_NOW,
                updated_at=FIXED_NOW,
            )
        )
        projection = ExecutionProjection(
            run_id=run_id,
            source="test",
            schema_version="1.0.0",
            lifecycle=Lifecycle.FAILED,
            outcome=Outcome.FAILED,
            validation=Validation.NOT_RUN,
            scope=Scope.CLEAN,
            started_at=FIXED_NOW,
            completed_at=FIXED_NOW + timedelta(minutes=5),
            decisions=[],
            evidence_refs=[],
            roles=[],
        )
        storage.upsert_projection(
            run_id=run_id,
            projection_schema="execution_summary/v1",
            projection_version="1.0.0",
            source="test",
            projection_json=projection.model_dump(mode="json"),
            lifecycle_status="failed",
        )


def test_version_command_smoke() -> None:
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip()


def test_evidence_audit_valid_package_exits_zero() -> None:
    result = CliRunner().invoke(app, ["evidence-audit", str(SECOND_PRODUCER)])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["run_id"] == "run-second-producer-001"


def test_evidence_audit_invalid_package_exits_nonzero() -> None:
    result = CliRunner().invoke(app, ["evidence-audit", str(INVALID_DUPLICATE)])
    assert result.exit_code != 0
    assert "duplicates event_id" in result.stdout


def test_evidence_conformance_valid_package_exits_zero() -> None:
    result = CliRunner().invoke(app, ["evidence-conformance", str(SECOND_PRODUCER)])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["package_valid"] is True
    assert data["run_id"] == "run-second-producer-001"


def test_evidence_conformance_invalid_package_exits_nonzero() -> None:
    result = CliRunner().invoke(
        app, ["evidence-conformance", str(INVALID_DUPLICATE)]
    )
    assert result.exit_code != 0
    data = json.loads(result.stdout)
    assert data["package_valid"] is False


def test_correlate_failures_json_reports_recurrent_finite_input(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.sqlite"
    _make_storage_with_failed_runs(db_path, ["run-a", "run-b"])

    result = CliRunner().invoke(
        app,
        ["--db", str(db_path), "correlate-failures", "run-a", "run-b", "--format", "json"],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["run_ids"] == ["run-a", "run-b"]
    assert data["recurrence"] == "recurrent"
    assert data["retry_safety"] == "unsafe"
    assert data["recommendation"] == "repair_runtime"
    assert data["recommendation"] != "accept"


def test_correlate_failures_uses_only_supplied_runs_no_discovery(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.sqlite"
    # Three equivalent failing runs exist, but only one is supplied.
    _make_storage_with_failed_runs(db_path, ["run-a", "run-b", "run-c"])

    result = CliRunner().invoke(
        app,
        ["--db", str(db_path), "correlate-failures", "run-a", "--format", "json"],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    # No storage scan discovered run-b/run-c; input is exactly the supplied run.
    assert data["run_ids"] == ["run-a"]
    assert data["recurrence"] == "single"
    assert data["retry_safety"] == "safe"


def test_correlate_failures_nonexistent_run_fails(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.sqlite"
    _make_storage_with_failed_runs(db_path, ["run-a"])

    result = CliRunner().invoke(
        app,
        ["--db", str(db_path), "correlate-failures", "run-a", "run-missing"],
    )
    assert result.exit_code != 0
    assert "run not found: run-missing" in result.output


def test_correlate_failures_omitted_run_ids_fails(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.sqlite"
    _make_storage_with_failed_runs(db_path, ["run-a"])

    result = CliRunner().invoke(
        app,
        ["--db", str(db_path), "correlate-failures"],
    )
    assert result.exit_code != 0
