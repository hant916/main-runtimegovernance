from __future__ import annotations

import json
import shutil
from pathlib import Path

from ailuros.adapters.evidence_package import validate_evidence_package_contract
from ailuros.core.validation import ValidationResult

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures" / "evidence_package"
VALID_V1 = FIXTURES / "valid-v1"
VALID_V15 = FIXTURES / "valid-v15"


def _copy_valid(src: Path, tmp_path: Path) -> Path:
    dest = tmp_path / "pkg"
    shutil.copytree(src, dest)
    return dest


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# --- T1: v1 detection / v1.5 backward compatibility ---

def test_valid_v1_contract():
    result = validate_evidence_package_contract(VALID_V1)
    assert isinstance(result, ValidationResult)
    assert result.ok is True
    assert result.errors == []
    assert result.warnings == []
    assert result.source == "sample-agent-v1"
    assert result.schema_version == "ailuros.timeline.v1"
    assert result.run_id == "run-v1-001"
    assert result.events_count == 2


def test_valid_v15_fixture_still_passes_on_existing_path():
    result = validate_evidence_package_contract(VALID_V15)
    assert result.ok is True
    assert result.errors == []
    assert result.schema_version == "ailuros.timeline.v0"


# --- T2: identity and event uniqueness ---

def test_duplicate_event_ids_fail_v1(tmp_path):
    pkg = _copy_valid(VALID_V1, tmp_path)
    timeline = json.loads((pkg / "timeline.json").read_text(encoding="utf-8"))
    timeline["events"].append(dict(timeline["events"][0]))
    _write_json(pkg / "timeline.json", timeline)

    result = validate_evidence_package_contract(pkg)
    assert result.ok is False
    assert any("duplicate event_id" in e for e in result.errors)


def test_unique_event_ids_pass_v1(tmp_path):
    pkg = _copy_valid(VALID_V1, tmp_path)
    timeline = json.loads((pkg / "timeline.json").read_text(encoding="utf-8"))
    timeline["events"].append({
        "event_id": "evt-v1-003",
        "event_type": "custom_event",
        "timestamp": "2025-01-15T10:02:00+00:00",
        "payload": {},
        "metadata": {},
    })
    _write_json(pkg / "timeline.json", timeline)

    manifest = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
    manifest["pkg_metadata"]["coverage"]["events"] = 3
    _write_json(pkg / "manifest.json", manifest)

    result = validate_evidence_package_contract(pkg)
    assert result.ok is True
    assert result.errors == []


# --- T3: provenance safety ---

def test_provenance_source_artifact_with_dot_dot_slash_fails(tmp_path):
    pkg = _copy_valid(VALID_V1, tmp_path)
    manifest = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
    manifest["provenance"]["source_artifact"] = "../etc/passwd"
    _write_json(pkg / "manifest.json", manifest)

    result = validate_evidence_package_contract(pkg)
    assert result.ok is False
    assert any("provenance.source_artifact" in e for e in result.errors)


def test_provenance_source_artifact_with_absolute_unix_path_fails(tmp_path):
    pkg = _copy_valid(VALID_V1, tmp_path)
    manifest = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
    manifest["provenance"]["source_artifact"] = "/etc/passwd"
    _write_json(pkg / "manifest.json", manifest)

    result = validate_evidence_package_contract(pkg)
    assert result.ok is False
    assert any("provenance.source_artifact" in e for e in result.errors)


def test_provenance_source_artifact_with_absolute_windows_path_fails(tmp_path):
    pkg = _copy_valid(VALID_V1, tmp_path)
    manifest = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
    manifest["provenance"]["source_artifact"] = "D:\\secrets\\key.txt"
    _write_json(pkg / "manifest.json", manifest)

    result = validate_evidence_package_contract(pkg)
    assert result.ok is False
    assert any("provenance.source_artifact" in e for e in result.errors)


def test_provenance_source_pointer_with_dot_dot_slash_fails(tmp_path):
    pkg = _copy_valid(VALID_V1, tmp_path)
    manifest = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
    manifest["provenance"]["source_pointer"] = "../../config"
    _write_json(pkg / "manifest.json", manifest)

    result = validate_evidence_package_contract(pkg)
    assert result.ok is False
    assert any("provenance.source_pointer" in e for e in result.errors)


def test_provenance_with_clean_logical_refs_passes(tmp_path):
    pkg = _copy_valid(VALID_V1, tmp_path)
    manifest = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
    manifest["provenance"]["source_artifact"] = "agent-v2"
    manifest["provenance"]["source_pointer"] = "pipeline/run-99/step-3"
    _write_json(pkg / "manifest.json", manifest)

    result = validate_evidence_package_contract(pkg)
    assert result.ok is True
    assert result.errors == []


def test_no_provenance_is_ok_v1(tmp_path):
    pkg = _copy_valid(VALID_V1, tmp_path)
    manifest = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
    del manifest["provenance"]
    _write_json(pkg / "manifest.json", manifest)

    result = validate_evidence_package_contract(pkg)
    assert result.ok is True
    assert result.errors == []


# --- T4: counts / digest declarations ---

def test_coverage_events_count_mismatch_fails(tmp_path):
    pkg = _copy_valid(VALID_V1, tmp_path)
    manifest = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
    manifest["pkg_metadata"]["coverage"]["events"] = 5
    _write_json(pkg / "manifest.json", manifest)

    result = validate_evidence_package_contract(pkg)
    assert result.ok is False
    assert any("pkg_metadata.coverage.events" in e for e in result.errors)


def test_coverage_files_count_mismatch_fails(tmp_path):
    pkg = _copy_valid(VALID_V1, tmp_path)
    manifest = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
    manifest["pkg_metadata"]["coverage"]["files"] = 10
    _write_json(pkg / "manifest.json", manifest)

    result = validate_evidence_package_contract(pkg)
    assert result.ok is False
    assert any("pkg_metadata.coverage.files" in e for e in result.errors)


def test_coverage_counts_match_passes(tmp_path):
    pkg = _copy_valid(VALID_V1, tmp_path)
    manifest = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
    manifest["pkg_metadata"]["coverage"]["events"] = 2
    manifest["pkg_metadata"]["coverage"]["files"] = 3
    _write_json(pkg / "manifest.json", manifest)

    result = validate_evidence_package_contract(pkg)
    assert result.ok is True
    assert result.errors == []


def test_no_pkg_metadata_is_ok_v1(tmp_path):
    pkg = _copy_valid(VALID_V1, tmp_path)
    manifest = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
    del manifest["pkg_metadata"]
    _write_json(pkg / "manifest.json", manifest)

    result = validate_evidence_package_contract(pkg)
    assert result.ok is True
    assert result.errors == []


def test_coverage_without_events_key_is_ok(tmp_path):
    pkg = _copy_valid(VALID_V1, tmp_path)
    manifest = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
    manifest["pkg_metadata"]["coverage"] = {"files": 3}
    _write_json(pkg / "manifest.json", manifest)

    result = validate_evidence_package_contract(pkg)
    assert result.ok is True
    assert result.errors == []
