from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.process_clarify_evidence_data import _check_raw_log

SAMPLE_DIR = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "clarify"
    / "evidence_bundle.sample"
)


def _copy_bundle(tmp_path: Path, name: str = "bundle") -> Path:
    dest = tmp_path / name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(SAMPLE_DIR, dest)
    return dest


def test_main_pass_via_subprocess(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.process_clarify_evidence_data",
            "--bundle",
            str(bundle_dir),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert (bundle_dir / "ailuros-validation-result.json").is_file()
    assert (bundle_dir / "ailuros-validation-report.md").is_file()


def test_main_missing_bundle_dir(tmp_path: Path) -> None:
    missing = tmp_path / "nonexistent"
    result = subprocess.run(
        [sys.executable, "-m", "scripts.process_clarify_evidence_data", "--bundle", str(missing)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "not found" in result.stderr


def test_main_no_args(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "scripts.process_clarify_evidence_data"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Usage" in result.stderr


def test_check_raw_log_missing(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    (bundle_dir / "clarify-validation.log").unlink()
    assert _check_raw_log(bundle_dir) == "raw_log_missing"


def test_check_raw_log_empty(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    (bundle_dir / "clarify-validation.log").write_text("", encoding="utf-8")
    assert _check_raw_log(bundle_dir) == "raw_log_empty"


def test_check_raw_log_ok(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    (bundle_dir / "clarify-validation.log").write_text("some log content\n", encoding="utf-8")
    assert _check_raw_log(bundle_dir) is None


def test_main_creates_output_files(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.process_clarify_evidence_data",
            "--bundle",
            str(bundle_dir),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    result_json = bundle_dir / "ailuros-validation-result.json"
    report_md = bundle_dir / "ailuros-validation-report.md"
    assert result_json.is_file()
    assert report_md.is_file()

    data = json.loads(result_json.read_text(encoding="utf-8"))
    assert data["schema_version"] == "ailuros.validation_result.v0"
    assert data["source"] == "clarify"
    assert data["status"] == "PASS"
