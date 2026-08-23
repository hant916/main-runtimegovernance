from __future__ import annotations

import json
import shutil
from pathlib import Path

from ailuros.adapters.evidence_package import validate_evidence_package_contract
from ailuros.core.validation import ValidationResult

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures" / "evidence_package"
VALID_PKG = FIXTURES / "valid-v15"


def _copy_valid(tmp_path: Path) -> Path:
    dest = tmp_path / "pkg"
    shutil.copytree(VALID_PKG, dest)
    return dest


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_valid_contract():
    result = validate_evidence_package_contract(VALID_PKG)
    assert isinstance(result, ValidationResult)
    assert result.ok is True
    assert result.errors == []
    assert result.warnings == []
    assert result.source == "sample-agent"
    assert result.schema_version == "ailuros.timeline.v0"
    assert result.run_id == "run-sample-001"
    assert result.events_count == 2


def test_schema_version_mismatch(tmp_path):
    pkg = _copy_valid(tmp_path)
    timeline = json.loads((pkg / "timeline.json").read_text(encoding="utf-8"))
    timeline["schema_version"] = "ailuros.timeline.v999"
    _write_json(pkg / "timeline.json", timeline)

    result = validate_evidence_package_contract(pkg)
    assert result.ok is False
    assert any("schema_version does not match" in e for e in result.errors)


def test_run_id_mismatch(tmp_path):
    pkg = _copy_valid(tmp_path)
    timeline = json.loads((pkg / "timeline.json").read_text(encoding="utf-8"))
    timeline["run_id"] = "run-other-999"
    _write_json(pkg / "timeline.json", timeline)

    result = validate_evidence_package_contract(pkg)
    assert result.ok is False
    assert any("run_id does not match" in e for e in result.errors)


def test_missing_events_array(tmp_path):
    pkg = _copy_valid(tmp_path)
    timeline = json.loads((pkg / "timeline.json").read_text(encoding="utf-8"))
    del timeline["events"]
    _write_json(pkg / "timeline.json", timeline)

    result = validate_evidence_package_contract(pkg)
    assert result.ok is False
    assert any("'events' must be an array" in e for e in result.errors)


def test_empty_events(tmp_path):
    pkg = _copy_valid(tmp_path)
    timeline = json.loads((pkg / "timeline.json").read_text(encoding="utf-8"))
    timeline["events"] = []
    _write_json(pkg / "timeline.json", timeline)

    result = validate_evidence_package_contract(pkg)
    assert result.ok is False
    assert any("'events' must not be empty" in e for e in result.errors)


def test_missing_event_type(tmp_path):
    pkg = _copy_valid(tmp_path)
    timeline = json.loads((pkg / "timeline.json").read_text(encoding="utf-8"))
    del timeline["events"][0]["event_type"]
    _write_json(pkg / "timeline.json", timeline)

    result = validate_evidence_package_contract(pkg)
    assert result.ok is False
    assert any("missing event_type" in e for e in result.errors)


def test_invalid_timestamp(tmp_path):
    pkg = _copy_valid(tmp_path)
    timeline = json.loads((pkg / "timeline.json").read_text(encoding="utf-8"))
    timeline["events"][0]["timestamp"] = "not-a-timestamp"
    _write_json(pkg / "timeline.json", timeline)

    result = validate_evidence_package_contract(pkg)
    assert result.ok is False
    assert any("invalid timestamp" in e for e in result.errors)


def test_unknown_event_type_is_warning(tmp_path):
    pkg = _copy_valid(tmp_path)
    timeline = json.loads((pkg / "timeline.json").read_text(encoding="utf-8"))
    timeline["events"][0]["event_type"] = "custom_unknown_event"
    _write_json(pkg / "timeline.json", timeline)

    result = validate_evidence_package_contract(pkg)
    assert result.ok is True
    assert result.errors == []
    assert any("unknown event_type" in w for w in result.warnings)


def test_optional_missing_file_does_not_fail(tmp_path):
    # The valid fixture lists notes.md as optional and does not ship it.
    pkg = _copy_valid(tmp_path)
    assert not (pkg / "notes.md").exists()

    result = validate_evidence_package_contract(pkg)
    assert result.ok is True
    assert result.errors == []


def test_required_missing_file_fails(tmp_path):
    pkg = _copy_valid(tmp_path)
    manifest = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
    manifest["files"].append({"name": "summary.json", "required": True})
    _write_json(pkg / "manifest.json", manifest)

    result = validate_evidence_package_contract(pkg)
    assert result.ok is False
    assert any("required file missing: summary.json" in e for e in result.errors)


def test_malformed_scope_ref_is_error(tmp_path):
    pkg = _copy_valid(tmp_path)
    timeline = json.loads((pkg / "timeline.json").read_text(encoding="utf-8"))
    timeline["events"][0]["scope_ref"] = 42
    _write_json(pkg / "timeline.json", timeline)

    result = validate_evidence_package_contract(pkg)
    assert result.ok is False
    assert any("scope_ref must be a string" in e for e in result.errors)


def test_valid_string_scope_ref_passes(tmp_path):
    pkg = _copy_valid(tmp_path)
    timeline = json.loads((pkg / "timeline.json").read_text(encoding="utf-8"))
    timeline["events"][0]["scope_ref"] = "scope-ok"
    _write_json(pkg / "timeline.json", timeline)

    result = validate_evidence_package_contract(pkg)
    assert result.ok is True
    assert result.errors == []
