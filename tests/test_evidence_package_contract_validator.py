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


# ── pkg_metadata.source_digest well-formedness ──────────────────────────────
#
# `source_digest` is a producer attestation about the upstream source material
# the exporter read. Ailuros never receives that material, so the value is
# structurally unverifiable and is NOT an integrity proof of the package files.
# What is checkable is its shape: a value that looks like a digest but is not
# one is misleading inside an audit record, so it is surfaced as a warning
# (never an error — a malformed attestation does not invalidate the evidence).

VALID_V1_PKG = FIXTURES / "valid-v1"


def _copy_valid_v1(tmp_path: Path) -> Path:
    dest = tmp_path / "pkg-v1"
    shutil.copytree(VALID_V1_PKG, dest)
    return dest


def _set_source_digest(pkg: Path, value: object) -> None:
    manifest = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
    manifest.setdefault("pkg_metadata", {})["source_digest"] = value
    _write_json(pkg / "manifest.json", manifest)


def _digest_warnings(result) -> list[str]:
    return [w for w in result.warnings if "source_digest" in w]


def test_absent_source_digest_is_valid_and_unremarked(tmp_path):
    """Omitting the attestation is the honest default and must stay silent."""
    pkg = _copy_valid_v1(tmp_path)
    manifest = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
    manifest.get("pkg_metadata", {}).pop("source_digest", None)
    _write_json(pkg / "manifest.json", manifest)

    result = validate_evidence_package_contract(pkg)
    assert result.ok is True
    assert _digest_warnings(result) == []


def test_well_formed_source_digest_is_accepted_silently(tmp_path):
    pkg = _copy_valid_v1(tmp_path)
    _set_source_digest(pkg, "sha256:" + "a" * 64)

    result = validate_evidence_package_contract(pkg)
    assert result.ok is True
    assert _digest_warnings(result) == []


def test_placeholder_source_digest_is_warned_not_silently_accepted(tmp_path):
    """The exact defect this check exists for: a `sha256:`-prefixed string that
    is not a digest at all must not pass as an integrity-looking audit field."""
    pkg = _copy_valid_v1(tmp_path)
    _set_source_digest(pkg, "sha256:everrun-postfix-minimal-fixture")

    result = validate_evidence_package_contract(pkg)
    assert result.ok is True, "a malformed attestation must not invalidate evidence"
    warnings = _digest_warnings(result)
    assert len(warnings) == 1
    assert "not a 64-character lowercase hex digest" in warnings[0]
    assert "unverified producer attestation" in warnings[0]


def test_source_digest_without_algorithm_prefix_is_warned(tmp_path):
    pkg = _copy_valid_v1(tmp_path)
    _set_source_digest(pkg, "a" * 64)

    result = validate_evidence_package_contract(pkg)
    assert result.ok is True
    assert any("not in '<algo>:<hex>' form" in w for w in _digest_warnings(result))


def test_source_digest_with_unknown_algorithm_is_warned(tmp_path):
    pkg = _copy_valid_v1(tmp_path)
    _set_source_digest(pkg, "crc32:deadbeef")

    result = validate_evidence_package_contract(pkg)
    assert result.ok is True
    assert any("unknown digest algorithm" in w for w in _digest_warnings(result))


def test_uppercase_hex_source_digest_is_warned(tmp_path):
    """Digests are compared as lowercase hex; uppercase would break equality."""
    pkg = _copy_valid_v1(tmp_path)
    _set_source_digest(pkg, "sha256:" + "A" * 64)

    result = validate_evidence_package_contract(pkg)
    assert result.ok is True
    assert _digest_warnings(result)


def test_empty_source_digest_is_warned(tmp_path):
    pkg = _copy_valid_v1(tmp_path)
    _set_source_digest(pkg, "   ")

    result = validate_evidence_package_contract(pkg)
    assert result.ok is True
    assert any("must be a non-empty string" in w for w in _digest_warnings(result))


def test_canonical_fixtures_declare_no_fabricated_source_digest():
    """Regression guard: the committed canonical fixtures must never carry a
    placeholder digest again. They have no real upstream digest available, so
    the honest representation is to omit the field."""
    repo_root = HERE.parent
    for name in ("everrun-postfix-minimal", "second-producer"):
        pkg = repo_root / "fixtures" / "runtime-evidence" / name
        result = validate_evidence_package_contract(pkg)
        assert _digest_warnings(result) == [], (
            f"{name} declares a malformed source_digest: {result.warnings}"
        )
        manifest = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
        assert "source_digest" not in manifest.get("pkg_metadata", {})


def test_non_ascii_package_loads_regardless_of_platform_default_encoding(tmp_path):
    """Regression: JSON must be read as UTF-8, not the platform default codepage.

    On a non-UTF-8 default locale (e.g. cp1252/cp936 Windows) a bare
    `Path.read_text()` raises UnicodeDecodeError on any non-ASCII byte. Every
    JSON read on the evidence path is pinned to utf-8; this locks that.
    """
    pkg = _copy_valid_v1(tmp_path)
    manifest = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
    manifest.setdefault("metadata", {})["description"] = "治理证据包 — ünïcodé ✓"
    _write_json(pkg / "manifest.json", manifest)

    result = validate_evidence_package_contract(pkg)
    assert result.ok is True
    assert result.errors == []
