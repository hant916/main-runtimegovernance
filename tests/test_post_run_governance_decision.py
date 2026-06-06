from __future__ import annotations

import json
import shutil
from pathlib import Path

from ailuros.adapters.evidence_package import (
    audit_evidence_package,
    audit_result_to_dict,
    audit_result_to_json,
)
from ailuros.core.audit import AuditDecision, AuditResult

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures" / "evidence_package"
VALID_PKG = FIXTURES / "valid-v15"


def _copy_valid(tmp_path: Path) -> Path:
    dest = tmp_path / "pkg"
    shutil.copytree(VALID_PKG, dest)
    return dest


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_clean_package_passes():
    result = audit_evidence_package(VALID_PKG)
    assert isinstance(result, AuditResult)
    assert result.decision is AuditDecision.PASS
    assert result.ok is True
    assert result.errors == []
    assert result.warnings == []
    assert result.governance_mode == "observe"
    assert result.source == "sample-agent"
    assert result.run_id == "run-sample-001"
    assert result.events_count == 2
    assert result.rules_evaluated == 2


def test_unknown_event_warns(tmp_path):
    pkg = _copy_valid(tmp_path)
    timeline = json.loads((pkg / "timeline.json").read_text(encoding="utf-8"))
    timeline["events"][0]["event_type"] = "custom_unknown_event"
    _write_json(pkg / "timeline.json", timeline)

    result = audit_evidence_package(pkg)
    assert result.decision is AuditDecision.WARN
    assert result.ok is True
    assert result.errors == []
    assert any("unknown event_type" in w for w in result.warnings)


def test_required_file_failure(tmp_path):
    pkg = _copy_valid(tmp_path)
    manifest = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
    manifest["files"].append({"name": "summary.json", "required": True})
    _write_json(pkg / "manifest.json", manifest)

    result = audit_evidence_package(pkg)
    assert result.decision is AuditDecision.FAIL
    assert result.ok is False
    assert any("required file missing: summary.json" in e for e in result.errors)


def test_errors_take_priority_over_warnings(tmp_path):
    # A package with both an unknown event (warning) and a missing required file
    # (error) must fail, not warn.
    pkg = _copy_valid(tmp_path)
    timeline = json.loads((pkg / "timeline.json").read_text(encoding="utf-8"))
    timeline["events"][0]["event_type"] = "custom_unknown_event"
    _write_json(pkg / "timeline.json", timeline)
    manifest = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
    manifest["files"].append({"name": "summary.json", "required": True})
    _write_json(pkg / "manifest.json", manifest)

    result = audit_evidence_package(pkg)
    assert result.decision is AuditDecision.FAIL
    assert result.ok is False
    assert result.warnings  # warning is still surfaced alongside the failure


def test_deterministic_json_output(tmp_path):
    pkg = _copy_valid(tmp_path)

    first = audit_result_to_json(audit_evidence_package(pkg))
    second = audit_result_to_json(audit_evidence_package(pkg))
    assert first == second

    data = json.loads(first)
    assert data["decision"] == "pass"
    assert data["ok"] is True
    assert data["rules_evaluated"] == 2
    assert data["warnings"] == []
    assert data["errors"] == []
    # Keys are sorted for stable output.
    assert list(data.keys()) == sorted(data.keys())


def test_only_three_decisions_exist():
    assert {d.value for d in AuditDecision} == {"pass", "warn", "fail"}


def test_to_dict_is_json_serializable():
    data = audit_result_to_dict(audit_evidence_package(VALID_PKG))
    # Round-trips through JSON without custom encoders.
    assert json.loads(json.dumps(data)) == data
