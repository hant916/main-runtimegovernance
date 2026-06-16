from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.run_clarify_data_pipeline import _fail_result


def _make_fake_clarify_root(tmp_path: Path, name: str = "clarify") -> Path:
    root = tmp_path / name
    root.mkdir(parents=True)
    (root / "package.json").write_text('{"name": "clarify"}', encoding="utf-8")
    bundle = root / "artifacts" / "ailuros" / "latest"
    bundle.mkdir(parents=True)
    _write_fake_bundle_files(bundle)
    return root


def _write_fake_bundle_files(bundle: Path) -> None:
    manifest = {
        "schema_version": "ailuros.evidence_bundle.v0",
        "producer": "clarify",
        "runtime_integration": "ailuros",
        "bundle_id": "test-bundle-001",
        "artifacts": [
            "ailuros.timeline.v0.json",
            "clarify-validation-result.json",
            "clarify-validation.log",
        ],
    }
    (bundle / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    timeline = {
        "schema_version": "ailuros.timeline.v0",
        "run_id": "test-run",
        "created_at": "2026-06-17T00:00:00Z",
        "events": [
            {
                "event": "INPUT_CLASSIFIED",
                "run_id": "test-run",
                "timestamp": "2026-06-17T00:00:00Z",
                "data": {"input_type": "text"},
            },
            {
                "event": "LLM_REQUEST",
                "run_id": "test-run",
                "timestamp": "2026-06-17T00:00:01Z",
                "data": {"model": "gpt-4"},
            },
            {
                "event": "LLM_RESPONSE",
                "run_id": "test-run",
                "timestamp": "2026-06-17T00:00:02Z",
                "data": {"response_length": 100},
            },
            {
                "event": "EVALUATION_RESULT",
                "run_id": "test-run",
                "timestamp": "2026-06-17T00:00:03Z",
                "data": {
                    "quality_signals": {
                        "json_valid": True,
                        "sentence_too_long": False,
                        "contains_direct_advice": False,
                        "contains_decision_pressure": False,
                        "ambiguities_present": False,
                    }
                },
            },
            {
                "event": "OUTPUT_GENERATED",
                "run_id": "test-run",
                "timestamp": "2026-06-17T00:00:04Z",
                "data": {"output_length": 50},
            },
            {
                "event": "RUN_COMPLETED",
                "run_id": "test-run",
                "timestamp": "2026-06-17T00:00:05Z",
                "data": {"duration_ms": 5000},
            },
        ],
    }
    (bundle / "ailuros.timeline.v0.json").write_text(
        json.dumps(timeline, indent=2), encoding="utf-8"
    )

    clarify_result = {
        "schema_version": "clarify.validation_result.v0",
        "status": "passed",
        "commands": [
            {
                "command": "check_policy",
                "exit_code": 0,
                "status": "passed",
                "duration_ms": 100,
            }
        ],
    }
    (bundle / "clarify-validation-result.json").write_text(
        json.dumps(clarify_result, indent=2), encoding="utf-8"
    )

    (bundle / "clarify-validation.log").write_text(
        "INFO: validation complete\n", encoding="utf-8"
    )
    (bundle / "README.md").write_text("# Evidence Bundle\n", encoding="utf-8")


def _run_pipeline(
    tmp_path: Path, args: list[str]
) -> subprocess.CompletedProcess:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "run_clarify_data_pipeline.py"
    )
    result = subprocess.run(
        [sys.executable, str(script)] + args,
        capture_output=True,
        text=True,
    )
    return result


def test_missing_clarify_root(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    out = tmp_path / "out"
    result = _run_pipeline(
        tmp_path,
        [
            "--clarify-root",
            str(missing),
            "--output",
            str(out),
            "--skip-clarify-command",
        ],
    )
    assert result.returncode == 1
    assert "does not exist" in result.stderr


def test_missing_package_json(tmp_path: Path) -> None:
    root = tmp_path / "clarify"
    root.mkdir()
    result = _run_pipeline(
        tmp_path,
        [
            "--clarify-root",
            str(root),
            "--output",
            str(tmp_path / "out"),
            "--skip-clarify-command",
        ],
    )
    assert result.returncode == 1
    assert "package.json" in result.stderr


def test_valid_fake_bundle_with_skip(tmp_path: Path) -> None:
    root = _make_fake_clarify_root(tmp_path)
    out = tmp_path / "out"
    result = _run_pipeline(
        tmp_path,
        [
            "--clarify-root",
            str(root),
            "--output",
            str(out),
            "--skip-clarify-command",
        ],
    )
    assert result.returncode == 0
    assert out.is_dir()
    assert (out / "manifest.json").is_file()
    assert (out / "ailuros.timeline.v0.json").is_file()
    assert (out / "clarify-validation-result.json").is_file()
    assert (out / "ailuros-validation-result.json").is_file()
    assert (out / "ailuros-validation-report.md").is_file()
    assert "Ailuros Clarify data pipeline: PASS" in result.stdout


def test_command_failure_bundle_missing(tmp_path: Path) -> None:
    root = tmp_path / "clarify"
    root.mkdir()
    (root / "package.json").write_text("{}", encoding="utf-8")
    out = tmp_path / "out"
    result = _run_pipeline(
        tmp_path,
        [
            "--clarify-root",
            str(root),
            "--output",
            str(out),
            "--skip-clarify-command",
        ],
    )
    assert result.returncode == 1
    result_json = out / "ailuros-validation-result.json"
    assert result_json.is_file()
    data = json.loads(result_json.read_text(encoding="utf-8"))
    assert data["status"] == "FAIL"
    assert data["source"] == "clarify"
    assert any(c["check"] == "clarify_bundle_exists" for c in data["checks"])
    report = out / "ailuros-validation-report.md"
    assert report.is_file()
    assert "FAIL" in report.read_text(encoding="utf-8")


def test_missing_processor(tmp_path: Path) -> None:
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    processor = scripts_dir / "process_clarify_evidence_data.py"
    if not processor.is_file():
        pytest.skip("Processor not found in scripts dir")
    backup = tmp_path / "process_clarify_evidence_data.py.bak"
    shutil.copy2(processor, backup)
    try:
        processor.unlink()
        root = _make_fake_clarify_root(tmp_path)
        out = tmp_path / "out"
        result = _run_pipeline(
            tmp_path,
            [
                "--clarify-root",
                str(root),
                "--output",
                str(out),
                "--skip-clarify-command",
            ],
        )
        assert result.returncode == 1
        assert "Processor not found" in result.stderr
    finally:
        shutil.copy2(backup, processor)


def test_fail_result(tmp_path: Path) -> None:
    out = tmp_path / "out"
    clarify_root = tmp_path / "clarify"
    clarify_root.mkdir(parents=True)
    _fail_result(out, clarify_root)

    result_json = out / "ailuros-validation-result.json"
    assert result_json.is_file()
    data = json.loads(result_json.read_text(encoding="utf-8"))
    assert data["status"] == "FAIL"
    assert data["source"] == "clarify"

    report = out / "ailuros-validation-report.md"
    assert report.is_file()
    assert "FAIL" in report.read_text(encoding="utf-8")
