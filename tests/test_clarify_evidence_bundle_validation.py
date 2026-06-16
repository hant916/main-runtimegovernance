from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from scripts.validate_clarify_evidence_bundle import (
    CheckResult,
    REQUIRED_EVENT_ORDER,
    REQUIRED_QUALITY_SIGNALS,
    validate_bundle,
    write_results,
)

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


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
        return None
    except (json.JSONDecodeError, OSError):
        return None


def test_valid_pass(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    checks, status = validate_bundle(bundle_dir)
    assert status == "PASS", f"Expected PASS, got {status}: {[c.message for c in checks if c.status != 'PASS']}"


def test_missing_manifest(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    (bundle_dir / "manifest.json").unlink()
    checks, status = validate_bundle(bundle_dir)
    assert status == "FAIL"
    assert any("manifest.json is missing" in c.message for c in checks)


def test_invalid_manifest_json(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    (bundle_dir / "manifest.json").write_text("not json", encoding="utf-8")
    checks, status = validate_bundle(bundle_dir)
    assert status == "FAIL"
    assert any("invalid JSON" in c.message for c in checks)


def test_missing_artifact(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    (bundle_dir / "clarify-validation.log").unlink()
    checks, status = validate_bundle(bundle_dir)
    assert status == "FAIL"
    assert any("Missing manifest artifacts" in c.message for c in checks)


def test_invalid_timeline_json(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    (bundle_dir / "ailuros.timeline.v0.json").write_text("not json", encoding="utf-8")
    checks, status = validate_bundle(bundle_dir)
    assert status == "FAIL"
    assert any("Timeline JSON is invalid" in c.message for c in checks)


def test_wrong_schema_version(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    manifest = _read_json(bundle_dir / "manifest.json")
    assert manifest is not None
    manifest["schema_version"] = "wrong.version"
    (bundle_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    checks, status = validate_bundle(bundle_dir)
    assert status == "FAIL"
    assert any("schema_version" in c.message for c in checks)


def test_wrong_event_count(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    timeline = _read_json(bundle_dir / "ailuros.timeline.v0.json")
    assert timeline is not None
    timeline["events"] = timeline["events"][:3]
    (bundle_dir / "ailuros.timeline.v0.json").write_text(json.dumps(timeline), encoding="utf-8")
    checks, status = validate_bundle(bundle_dir)
    assert status == "FAIL"
    assert any("events length" in c.message for c in checks)


def test_wrong_event_order(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    timeline = _read_json(bundle_dir / "ailuros.timeline.v0.json")
    assert timeline is not None
    events = list(timeline["events"])
    events[0], events[1] = events[1], events[0]
    timeline["events"] = events
    (bundle_dir / "ailuros.timeline.v0.json").write_text(json.dumps(timeline), encoding="utf-8")
    checks, status = validate_bundle(bundle_dir)
    assert status == "FAIL"
    assert any("event order" in c.message for c in checks)


def test_missing_quality_signals(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    timeline = _read_json(bundle_dir / "ailuros.timeline.v0.json")
    assert timeline is not None
    for ev in timeline["events"]:
        if ev["event"] == "EVALUATION_RESULT" and "data" in ev:
            del ev["data"]["quality_signals"]
            break
    (bundle_dir / "ailuros.timeline.v0.json").write_text(json.dumps(timeline), encoding="utf-8")
    checks, status = validate_bundle(bundle_dir)
    assert status == "FAIL"
    assert any("quality_signals is missing" in c.message for c in checks)


def test_non_boolean_signal(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    timeline = _read_json(bundle_dir / "ailuros.timeline.v0.json")
    assert timeline is not None
    for ev in timeline["events"]:
        if ev["event"] == "EVALUATION_RESULT" and "data" in ev:
            ev["data"]["quality_signals"]["json_valid"] = "yes"
            break
    (bundle_dir / "ailuros.timeline.v0.json").write_text(json.dumps(timeline), encoding="utf-8")
    checks, status = validate_bundle(bundle_dir)
    assert status == "FAIL"
    assert any("Non-boolean" in c.message for c in checks)


def test_failed_clarify_validation(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    clarify_result = _read_json(bundle_dir / "clarify-validation-result.json")
    assert clarify_result is not None
    clarify_result["status"] = "failed"
    (bundle_dir / "clarify-validation-result.json").write_text(
        json.dumps(clarify_result), encoding="utf-8"
    )
    checks, status = validate_bundle(bundle_dir)
    assert status == "FAIL"
    assert any("status is 'failed'" in c.message for c in checks)


def test_forbidden_field(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    manifest = _read_json(bundle_dir / "manifest.json")
    assert manifest is not None
    manifest["policy_decision"] = "blocked"
    (bundle_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    checks, status = validate_bundle(bundle_dir)
    assert status == "FAIL"
    assert any("Forbidden runtime/policy key" in c.message for c in checks)


def test_suspicious_secret_key_warning(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    manifest = _read_json(bundle_dir / "manifest.json")
    assert manifest is not None
    manifest["api_key"] = "sk-1234"
    (bundle_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    checks, status = validate_bundle(bundle_dir)
    assert status == "WARN"
    assert any("Suspicious secret-like key" in c.message for c in checks)


def test_local_path_warning(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    manifest = _read_json(bundle_dir / "manifest.json")
    assert manifest is not None
    manifest["local_path"] = "C:\\Users\\test"
    (bundle_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    checks, status = validate_bundle(bundle_dir)
    assert status == "WARN"
    assert any("Local machine reference" in c.message for c in checks)


def test_write_results_creates_files(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    checks, status = validate_bundle(bundle_dir)
    write_results(bundle_dir, checks, status)

    result_path = bundle_dir / "ailuros-validation-result.json"
    report_path = bundle_dir / "ailuros-validation-report.md"
    assert result_path.is_file()
    assert report_path.is_file()

    result = _read_json(result_path)
    assert result is not None
    assert result["schema_version"] == "ailuros.validation_result.v0"
    assert result["source"] == "clarify"
    assert result["status"] == "PASS"
    assert "checks" in result
    assert "summary" in result
