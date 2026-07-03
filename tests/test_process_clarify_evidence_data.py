from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

SAMPLE_DIR = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "clarify"
    / "evidence_bundle.sample"
)


def _copy_bundle(tmp_path: Path) -> Path:
    bundle_dir = tmp_path / "bundle"
    shutil.copytree(SAMPLE_DIR, bundle_dir)
    for generated in (
        "ailuros-validation-result.json",
        "ailuros-validation-report.md",
    ):
        generated_path = bundle_dir / generated
        if generated_path.exists():
            generated_path.unlink()
    return bundle_dir


def _run_processor(bundle_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/process_clarify_evidence_data.py",
            "--bundle",
            str(bundle_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )


def _read_result(bundle_dir: Path) -> dict:
    return json.loads((bundle_dir / "ailuros-validation-result.json").read_text())


def _read_json(bundle_dir: Path, filename: str) -> dict:
    return json.loads((bundle_dir / filename).read_text(encoding="utf-8"))


def _write_json(bundle_dir: Path, filename: str, data: dict) -> None:
    (bundle_dir / filename).write_text(
        json.dumps(data, indent=2) + "\n",
        encoding="utf-8",
    )


def test_valid_sample_bundle_returns_pass(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)

    completed = _run_processor(bundle_dir)
    result = _read_result(bundle_dir)

    assert completed.returncode == 0, completed.stderr
    assert (bundle_dir / "ailuros-validation-result.json").is_file()
    assert (bundle_dir / "ailuros-validation-report.md").is_file()
    assert result["status"] == "PASS"
    assert result["summary"]["timeline_events"] == 6
    assert result["summary"]["clarify_validation_status"] == "passed"


def test_missing_manifest_returns_fail(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    (bundle_dir / "manifest.json").unlink()

    completed = _run_processor(bundle_dir)
    result = _read_result(bundle_dir)

    assert completed.returncode == 1
    assert result["status"] == "FAIL"
    assert result["summary"]["blocking_issues"] > 0


def test_wrong_manifest_schema_returns_fail(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    manifest = _read_json(bundle_dir, "manifest.json")
    manifest["schema_version"] = "bad"
    _write_json(bundle_dir, "manifest.json", manifest)

    completed = _run_processor(bundle_dir)
    result = _read_result(bundle_dir)

    assert completed.returncode == 1
    assert result["status"] == "FAIL"


def test_runtime_integration_true_returns_fail(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    manifest = _read_json(bundle_dir, "manifest.json")
    manifest["runtime_integration"] = True
    _write_json(bundle_dir, "manifest.json", manifest)

    completed = _run_processor(bundle_dir)
    result = _read_result(bundle_dir)

    assert completed.returncode == 1
    assert result["status"] == "FAIL"


def test_wrong_timeline_event_order_returns_fail(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    timeline = _read_json(bundle_dir, "ailuros.timeline.v0.json")
    timeline["events"][0], timeline["events"][1] = (
        timeline["events"][1],
        timeline["events"][0],
    )
    _write_json(bundle_dir, "ailuros.timeline.v0.json", timeline)

    completed = _run_processor(bundle_dir)
    result = _read_result(bundle_dir)

    assert completed.returncode == 1
    assert result["status"] == "FAIL"


def test_missing_quality_signals_returns_fail(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    timeline = _read_json(bundle_dir, "ailuros.timeline.v0.json")
    del timeline["events"][3]["data"]["quality_signals"]
    _write_json(bundle_dir, "ailuros.timeline.v0.json", timeline)

    completed = _run_processor(bundle_dir)
    result = _read_result(bundle_dir)

    assert completed.returncode == 1
    assert result["status"] == "FAIL"


def test_non_boolean_quality_signal_returns_fail(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    timeline = _read_json(bundle_dir, "ailuros.timeline.v0.json")
    timeline["events"][3]["data"]["quality_signals"]["json_valid"] = "yes"
    _write_json(bundle_dir, "ailuros.timeline.v0.json", timeline)

    completed = _run_processor(bundle_dir)
    result = _read_result(bundle_dir)

    assert completed.returncode == 1
    assert result["status"] == "FAIL"


def test_clarify_skipped_validation_returns_warn(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    clarify_result = _read_json(bundle_dir, "clarify-validation-result.json")
    clarify_result["status"] = "skipped"
    clarify_result["commands"] = []
    _write_json(bundle_dir, "clarify-validation-result.json", clarify_result)

    completed = _run_processor(bundle_dir)
    result = _read_result(bundle_dir)

    assert completed.returncode == 0
    assert result["status"] == "WARN"
    assert result["summary"]["warnings"] > 0


def test_clarify_failed_validation_returns_fail(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    clarify_result = _read_json(bundle_dir, "clarify-validation-result.json")
    clarify_result["status"] = "failed"
    _write_json(bundle_dir, "clarify-validation-result.json", clarify_result)

    completed = _run_processor(bundle_dir)
    result = _read_result(bundle_dir)

    assert completed.returncode == 1
    assert result["status"] == "FAIL"


def test_forbidden_policy_field_returns_fail(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    timeline = _read_json(bundle_dir, "ailuros.timeline.v0.json")
    timeline["events"][3]["data"]["policy_decision"] = "block"
    _write_json(bundle_dir, "ailuros.timeline.v0.json", timeline)

    completed = _run_processor(bundle_dir)
    result = _read_result(bundle_dir)

    assert completed.returncode == 1
    assert result["status"] == "FAIL"


def test_suspicious_secret_like_key_returns_warn(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)
    timeline = _read_json(bundle_dir, "ailuros.timeline.v0.json")
    timeline["events"][3]["data"]["api_key"] = "dummy"
    _write_json(bundle_dir, "ailuros.timeline.v0.json", timeline)

    completed = _run_processor(bundle_dir)
    result = _read_result(bundle_dir)

    assert completed.returncode == 0
    assert result["status"] == "WARN"


def test_no_local_absolute_path_leakage(tmp_path: Path) -> None:
    bundle_dir = _copy_bundle(tmp_path)

    completed = _run_processor(bundle_dir)
    result_text = (bundle_dir / "ailuros-validation-result.json").read_text(
        encoding="utf-8"
    )

    assert completed.returncode == 0
    assert "C:\\" not in result_text
    assert "/Users/" not in result_text
