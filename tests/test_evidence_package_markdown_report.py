from __future__ import annotations

import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from ailuros.adapters.evidence_package import (
    audit_evidence_package,
    audit_result_to_markdown,
)
from ailuros.cli import app

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures" / "evidence_package"
VALID_PKG = FIXTURES / "valid-v15"
GOLDEN = HERE / "golden" / "evidence-package-v15-audit-report.md"

runner = CliRunner()


def _copy_valid(tmp_path: Path) -> Path:
    dest = tmp_path / "pkg"
    shutil.copytree(VALID_PKG, dest)
    return dest


def _render(package_dir: Path) -> str:
    return audit_result_to_markdown(audit_evidence_package(package_dir))


def test_report_contains_required_sections_and_fields():
    md = _render(VALID_PKG)
    # Core identity fields.
    assert "pass" in md
    assert "ailuros.timeline.v0" in md  # schema_version
    assert "run-sample-001" in md  # run_id
    # Required section headers.
    for header in (
        "## Decision",
        "## Summary",
        "## Checks",
        "## Warnings",
        "## Errors",
        "## Verdict",
    ):
        assert header in md
    # Decision is surfaced prominently.
    assert "**PASS**" in md
    # Checks table is present with a header row.
    assert "| Check | Status | Detail |" in md
    assert "Contract validation" in md
    # Verdict text.
    assert "Evidence is clean and contract-valid." in md


def test_warnings_and_errors_rendered_when_present(tmp_path):
    pkg = _copy_valid(tmp_path)
    timeline = json.loads((pkg / "timeline.json").read_text(encoding="utf-8"))
    timeline["events"][0]["event_type"] = "custom_unknown_event"
    (pkg / "timeline.json").write_text(json.dumps(timeline, indent=2), encoding="utf-8")

    md = _render(pkg)
    assert "**WARN**" in md
    assert "unknown event_type" in md
    # Errors section still renders its empty placeholder.
    assert "## Errors" in md
    assert "None." in md
    assert "Evidence is valid but has tolerated anomalies." in md


def test_output_is_deterministic(tmp_path):
    pkg = _copy_valid(tmp_path)
    assert _render(pkg) == _render(pkg)


def test_report_matches_golden():
    rendered = _render(VALID_PKG)
    golden = GOLDEN.read_text(encoding="utf-8")
    # Line-by-line comparison is robust to platform newline translation.
    assert rendered.splitlines() == golden.splitlines()


def test_cli_emits_markdown():
    result = runner.invoke(app, ["evidence-audit", str(VALID_PKG), "--format", "md"])
    assert result.exit_code == 0
    assert "# Evidence Package Audit Report" in result.stdout
    assert "**PASS**" in result.stdout


def test_cli_emits_json_by_default():
    result = runner.invoke(app, ["evidence-audit", str(VALID_PKG)])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["decision"] == "pass"
    assert data["run_id"] == "run-sample-001"


def test_cli_writes_out_file(tmp_path):
    out = tmp_path / "report.md"
    result = runner.invoke(
        app,
        ["evidence-audit", str(VALID_PKG), "--format", "md", "--out", str(out)],
    )
    assert result.exit_code == 0
    written = out.read_text(encoding="utf-8")
    assert written.splitlines() == _render(VALID_PKG).splitlines()


def test_cli_missing_package_errors(tmp_path):
    missing = tmp_path / "nope"
    result = runner.invoke(app, ["evidence-audit", str(missing)])
    # Exit code is the stable contract; the error text location (stdout vs
    # stderr) varies across click/typer versions, so it is not asserted here.
    assert result.exit_code == 1
