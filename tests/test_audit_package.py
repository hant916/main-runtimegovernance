from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ailuros.audit_package import export_audit_package_to_dir
from ailuros.cli import app
from ailuros.models import Environment, Run, RunStatus, RuntimeEvent, RuntimeEventType
from ailuros.storage import SQLiteStorage


def _make_run(storage: SQLiteStorage, run_id: str) -> Run:
    now = datetime.now(UTC)
    run = Run(
        run_id=run_id,
        agent_id="agent-1",
        environment=Environment.DEVELOPMENT,
        status=RunStatus.COMPLETED,
        input={"prompt": "test"},
        created_at=now,
        updated_at=now,
    )
    storage.create_run(run)
    return run


def _make_event(
    run_id: str,
    event_type: RuntimeEventType,
    payload: dict | None = None,
) -> RuntimeEvent:
    return RuntimeEvent(
        event_id=f"evt_{datetime.now(UTC).timestamp()}",
        run_id=run_id,
        event_type=event_type,
        timestamp=datetime.now(UTC),
        payload=payload or {},
    )


class TestAuditPackageExporter:
    def test_all_package_files_generated(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-ap-001")
        storage.append_event(_make_event("run-ap-001", RuntimeEventType.RUN_STARTED))

        output_dir = tmp_path / "packages"
        pkg_dir = export_audit_package_to_dir(storage, "run-ap-001", output_dir)

        assert pkg_dir == output_dir / "run-ap-001"
        assert (pkg_dir / "manifest.json").exists()
        assert (pkg_dir / "run.json").exists()
        assert (pkg_dir / "timeline.jsonl").exists()
        assert (pkg_dir / "decisions.json").exists()
        assert (pkg_dir / "evaluations.json").exists()
        assert (pkg_dir / "regressions.json").exists()
        assert (pkg_dir / "summary.md").exists()

    def test_manifest_contract(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-ap-002")
        storage.append_event(_make_event("run-ap-002", RuntimeEventType.RUN_STARTED))

        output_dir = tmp_path / "packages"
        pkg_dir = export_audit_package_to_dir(storage, "run-ap-002", output_dir)
        manifest = json.loads((pkg_dir / "manifest.json").read_text())

        assert manifest["schema_version"] == "ailuros.audit-package.v1"
        assert manifest["run_id"] == "run-ap-002"
        assert "generated_at" in manifest
        assert "files" in manifest
        assert "manifest.json" in manifest["files"]
        assert manifest["package_status"] == "complete"
        assert manifest["counts"]["timeline_events"] == 1
        assert "decisions" in manifest["counts"]
        assert "evaluations" in manifest["counts"]
        assert "regressions" in manifest["counts"]

    def test_missing_regressions_is_empty_array(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-ap-003")
        storage.append_event(_make_event("run-ap-003", RuntimeEventType.RUN_STARTED))

        output_dir = tmp_path / "packages"
        pkg_dir = export_audit_package_to_dir(storage, "run-ap-003", output_dir)
        regressions = json.loads((pkg_dir / "regressions.json").read_text())

        assert regressions == []

    def test_missing_evaluations_is_empty_array(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-ap-004")
        storage.append_event(_make_event("run-ap-004", RuntimeEventType.RUN_STARTED))

        output_dir = tmp_path / "packages"
        pkg_dir = export_audit_package_to_dir(storage, "run-ap-004", output_dir)
        evaluations = json.loads((pkg_dir / "evaluations.json").read_text())

        assert evaluations == []

    def test_summary_mentions_not_available_when_no_regressions(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-ap-005")
        storage.append_event(_make_event("run-ap-005", RuntimeEventType.RUN_STARTED))

        output_dir = tmp_path / "packages"
        pkg_dir = export_audit_package_to_dir(storage, "run-ap-005", output_dir)
        summary = (pkg_dir / "summary.md").read_text()

        assert "not_available" in summary

    def test_unknown_run_id_fails_cleanly(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()

        output_dir = tmp_path / "packages"
        with pytest.raises((LookupError, RuntimeError, OSError)):
            export_audit_package_to_dir(storage, "missing-run", output_dir)

        assert not (output_dir / "missing-run" / "manifest.json").exists()

    def test_deterministic_output(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-ap-006")
        storage.append_event(
            _make_event("run-ap-006", RuntimeEventType.GOVERNANCE_DECISION, {
                "decision": "allow",
                "reason": "safe",
            })
        )

        out1 = tmp_path / "out1"
        out2 = tmp_path / "out2"
        pkg1 = export_audit_package_to_dir(storage, "run-ap-006", out1)
        pkg2 = export_audit_package_to_dir(storage, "run-ap-006", out2)

        for file in ("run.json", "timeline.jsonl", "decisions.json",
                     "evaluations.json", "regressions.json", "summary.md"):
            content1 = (pkg1 / file).read_text()
            content2 = (pkg2 / file).read_text()
            assert content1 == content2, f"{file} is not deterministic"

    def test_existing_output_dir_overwrites_cleanly(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-ap-007")
        storage.append_event(_make_event("run-ap-007", RuntimeEventType.RUN_STARTED))

        output_dir = tmp_path / "packages"
        export_audit_package_to_dir(storage, "run-ap-007", output_dir)
        export_audit_package_to_dir(storage, "run-ap-007", output_dir)

        pkg_dir = output_dir / "run-ap-007"
        assert (pkg_dir / "manifest.json").exists()
        manifest = json.loads((pkg_dir / "manifest.json").read_text())
        assert manifest["package_status"] == "complete"

    def test_decisions_extracted_correctly(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-ap-008")
        storage.append_event(
            _make_event("run-ap-008", RuntimeEventType.GOVERNANCE_DECISION, {
                "decision": "allow",
                "reason": "all good",
                "tool_name": "bash",
            })
        )

        output_dir = tmp_path / "packages"
        pkg_dir = export_audit_package_to_dir(storage, "run-ap-008", output_dir)
        decisions = json.loads((pkg_dir / "decisions.json").read_text())

        assert len(decisions) == 1
        assert decisions[0]["decision"] == "allow"
        assert decisions[0]["tool_name"] == "bash"

    def test_timeline_jsonl_format(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-ap-009")
        storage.append_event(_make_event("run-ap-009", RuntimeEventType.RUN_STARTED))
        storage.append_event(_make_event("run-ap-009", RuntimeEventType.RUN_COMPLETED))

        output_dir = tmp_path / "packages"
        pkg_dir = export_audit_package_to_dir(storage, "run-ap-009", output_dir)
        lines = (pkg_dir / "timeline.jsonl").read_text().strip().split("\n")

        assert len(lines) == 2
        for line in lines:
            parsed = json.loads(line)
            assert "event_id" in parsed
            assert "event_type" in parsed
            assert "timestamp" in parsed


class TestAuditPackageCLI:
    def test_cli_audit_package_with_output_dir(self, tmp_path: Path) -> None:
        db = tmp_path / "runtime.sqlite"
        storage = SQLiteStorage(db)
        storage.init()
        _make_run(storage, "run-cli-001")
        storage.append_event(_make_event("run-cli-001", RuntimeEventType.RUN_STARTED))

        output_dir = tmp_path / "cli_packages"
        result = CliRunner().invoke(app, [
            "--db", str(db),
            "audit-package", "run-cli-001",
            "--output-dir", str(output_dir),
        ])

        assert result.exit_code == 0
        pkg_dir = output_dir / "run-cli-001"
        assert (pkg_dir / "manifest.json").exists()
        assert (pkg_dir / "run.json").exists()
        assert str(pkg_dir) in result.output

    def test_cli_audit_package_unknown_run(self, tmp_path: Path) -> None:
        db = tmp_path / "runtime.sqlite"
        SQLiteStorage(db).init()

        result = CliRunner().invoke(app, [
            "--db", str(db),
            "audit-package", "missing-run",
            "--output-dir", str(tmp_path / "packages"),
        ])

        assert result.exit_code != 0
        assert "missing-run" in result.output or "not found" in result.output.lower()

    def test_cli_audit_package_no_manifest_on_failure(self, tmp_path: Path) -> None:
        db = tmp_path / "runtime.sqlite"
        SQLiteStorage(db).init()

        output_dir = tmp_path / "packages"
        result = CliRunner().invoke(app, [
            "--db", str(db),
            "audit-package", "missing-run",
            "--output-dir", str(output_dir),
        ])

        assert result.exit_code != 0
        assert not (output_dir / "missing-run" / "manifest.json").exists()
