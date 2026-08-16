from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from ailuros.audit_package import validate_audit_package_dir
from ailuros.cli import app

REQUIRED_FILES = (
    "manifest.json",
    "run.json",
    "timeline.jsonl",
    "decisions.json",
    "evaluations.json",
    "regressions.json",
    "summary.md",
)


def _write_package(
    path: Path, *, run_id: str = "run-001", decisions: list[dict] | None = None
) -> Path:
    path.mkdir()
    payloads = {
        "manifest.json": {"run_id": run_id, "files": list(REQUIRED_FILES)},
        "run.json": {"run_id": run_id, "status": "completed"},
        "decisions.json": decisions or [],
        "evaluations.json": [],
        "regressions.json": [],
    }
    for file_name, payload in payloads.items():
        (path / file_name).write_text(json.dumps(payload), encoding="utf-8")
    (path / "timeline.jsonl").write_text(
        json.dumps({"event_id": "evt-1", "run_id": run_id, "event_type": "run_started"}),
        encoding="utf-8",
    )
    (path / "summary.md").write_text("# Summary\n", encoding="utf-8")
    return path


def test_valid_package_passes(tmp_path: Path) -> None:
    result = validate_audit_package_dir(_write_package(tmp_path / "pkg"))

    assert result.valid is True
    assert result.decision == "PASS"
    assert result.reasons == []


def test_missing_required_file_fails(tmp_path: Path) -> None:
    pkg = _write_package(tmp_path / "pkg")
    (pkg / "manifest.json").unlink()

    result = validate_audit_package_dir(pkg)

    assert result.valid is False
    assert result.decision == "FAIL"
    assert "missing required file: manifest.json" in result.reasons


def test_malformed_json_fails(tmp_path: Path) -> None:
    pkg = _write_package(tmp_path / "pkg")
    (pkg / "run.json").write_text("{bad", encoding="utf-8")

    result = validate_audit_package_dir(pkg)

    assert result.valid is False
    assert result.decision == "FAIL"
    assert result.reasons[0].startswith("malformed JSON in run.json")


def test_malformed_jsonl_fails_with_line_number(tmp_path: Path) -> None:
    pkg = _write_package(tmp_path / "pkg")
    (pkg / "timeline.jsonl").write_text('{"ok": true}\n{bad', encoding="utf-8")

    result = validate_audit_package_dir(pkg)

    assert result.valid is False
    assert result.decision == "FAIL"
    assert "malformed JSONL in timeline.jsonl: line 2" in result.reasons[0]


def test_mismatched_run_id_fails(tmp_path: Path) -> None:
    pkg = _write_package(tmp_path / "pkg")
    (pkg / "decisions.json").write_text(
        json.dumps([{"run_id": "other-run", "decision": "allow"}]),
        encoding="utf-8",
    )

    result = validate_audit_package_dir(pkg)

    assert result.valid is False
    assert result.decision == "FAIL"
    assert result.reasons == ["mismatched run_id values: other-run, run-001"]


def test_mismatched_timeline_run_id_fails(tmp_path: Path) -> None:
    pkg = _write_package(tmp_path / "pkg")
    (pkg / "timeline.jsonl").write_text(
        json.dumps({"event_id": "evt-1", "run_id": "other-run", "event_type": "run_started"}),
        encoding="utf-8",
    )

    result = validate_audit_package_dir(pkg)

    assert result.valid is False
    assert result.decision == "FAIL"
    assert result.reasons == ["mismatched run_id values: other-run, run-001"]


def test_mismatched_evaluation_run_id_fails(tmp_path: Path) -> None:
    pkg = _write_package(tmp_path / "pkg")
    (pkg / "evaluations.json").write_text(
        json.dumps([{"run_id": "other-run"}]),
        encoding="utf-8",
    )

    result = validate_audit_package_dir(pkg)

    assert result.valid is False
    assert result.decision == "FAIL"
    assert result.reasons == ["mismatched run_id values: other-run, run-001"]


def test_mismatched_regression_run_id_fails(tmp_path: Path) -> None:
    pkg = _write_package(tmp_path / "pkg")
    (pkg / "regressions.json").write_text(
        json.dumps([{"run_id": "other-run"}]),
        encoding="utf-8",
    )

    result = validate_audit_package_dir(pkg)

    assert result.valid is False
    assert result.decision == "FAIL"
    assert result.reasons == ["mismatched run_id values: other-run, run-001"]


def test_nested_noncanonical_metadata_run_id_is_ignored(tmp_path: Path) -> None:
    pkg = _write_package(
        tmp_path / "pkg",
        decisions=[
            {
                "run_id": "run-001",
                "decision": "allow",
                "metadata": {"run_id": "some-other-run"},
            }
        ],
    )

    result = validate_audit_package_dir(pkg)

    assert result.valid is True
    assert result.decision == "PASS"
    assert result.reasons == []


def test_nested_noncanonical_baseline_reference_run_id_is_ignored(tmp_path: Path) -> None:
    pkg = _write_package(tmp_path / "pkg")
    (pkg / "evaluations.json").write_text(
        json.dumps(
            [
                {
                    "run_id": "run-001",
                    "baseline": {"run_id": "baseline-run"},
                    "reference": {"run_id": "reference-run"},
                    "baseline_run_id": "another-baseline-run",
                }
            ]
        ),
        encoding="utf-8",
    )

    result = validate_audit_package_dir(pkg)

    assert result.valid is True
    assert result.decision == "PASS"
    assert result.reasons == []


def test_invalid_utf8_summary_fails_deterministically(tmp_path: Path) -> None:
    pkg = _write_package(tmp_path / "pkg")
    (pkg / "summary.md").write_bytes(b"\xff\xfe not valid utf-8")

    result = validate_audit_package_dir(pkg)

    assert result.valid is False
    assert result.decision == "FAIL"
    assert result.reasons == ["malformed text in summary.md: invalid UTF-8"]


def test_block_decision_fails(tmp_path: Path) -> None:
    result = validate_audit_package_dir(
        _write_package(tmp_path / "pkg", decisions=[{"run_id": "run-001", "decision": "block"}])
    )

    assert result.valid is True
    assert result.decision == "FAIL"
    assert result.reasons == ["blocking governance decision present"]


def test_review_decision_requires_review(tmp_path: Path) -> None:
    result = validate_audit_package_dir(
        _write_package(
            tmp_path / "pkg", decisions=[{"run_id": "run-001", "decision": "require_review"}]
        )
    )

    assert result.valid is True
    assert result.decision == "REVIEW_REQUIRED"
    assert result.reasons == ["review governance decision present"]


def test_validate_package_cli_outputs_json_and_fails_for_invalid_package(tmp_path: Path) -> None:
    pkg = _write_package(tmp_path / "pkg")
    (pkg / "run.json").unlink()

    result = CliRunner().invoke(app, ["validate-package", str(pkg)])

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload == {
        "valid": False,
        "decision": "FAIL",
        "reasons": ["missing required file: run.json"],
    }


def test_validate_package_cli_allows_review_exit_zero(tmp_path: Path) -> None:
    pkg = _write_package(tmp_path / "pkg", decisions=[{"run_id": "run-001", "decision": "review"}])

    result = CliRunner().invoke(app, ["validate-package", str(pkg)])

    assert result.exit_code == 0
    assert json.loads(result.output)["decision"] == "REVIEW_REQUIRED"


def test_validate_package_cli_fails_for_blocking_decision(tmp_path: Path) -> None:
    pkg = _write_package(tmp_path / "pkg", decisions=[{"run_id": "run-001", "decision": "block"}])

    result = CliRunner().invoke(app, ["validate-package", str(pkg)])

    assert result.exit_code != 0
    assert json.loads(result.output)["decision"] == "FAIL"


def test_validate_package_cli_emits_json_for_invalid_summary_utf8(tmp_path: Path) -> None:
    pkg = _write_package(tmp_path / "pkg")
    (pkg / "summary.md").write_bytes(b"\xff\xfe not valid utf-8")

    result = CliRunner().invoke(app, ["validate-package", str(pkg)])

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload == {
        "valid": False,
        "decision": "FAIL",
        "reasons": ["malformed text in summary.md: invalid UTF-8"],
    }
