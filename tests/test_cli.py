from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from ailuros.cli import app

HERE = Path(__file__).resolve().parent
SECOND_PRODUCER = HERE.parent / "fixtures" / "runtime-evidence" / "second-producer"
INVALID_DUPLICATE = SECOND_PRODUCER / "invalid" / "duplicate-event-id"


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
