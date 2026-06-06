from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from ailuros.adapters.evidence_package import load_evidence_package

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures" / "evidence_package"
VALID_PKG = FIXTURES / "valid-v15"


def test_load_valid_package():
    pkg = load_evidence_package(VALID_PKG)
    assert pkg.source == "sample-agent"
    assert pkg.schema_version == "ailuros.timeline.v0"
    assert pkg.run_id == "run-sample-001"
    assert len(pkg.events) == 2
    assert pkg.events[0].event_id == "evt-001"
    assert pkg.events[0].event_type == "run_started"
    assert pkg.files["manifest.json"] == "manifest.json"
    assert pkg.files["timeline.json"] == "timeline.json"


def test_load_valid_package_events_have_timezone():
    pkg = load_evidence_package(VALID_PKG)
    for ev in pkg.events:
        assert ev.timestamp.tzinfo is not None


def test_missing_package_dir():
    with pytest.raises(FileNotFoundError, match="Evidence package directory not found"):
        load_evidence_package("/tmp/nonexistent-evidence-pkg")


def test_missing_manifest():
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        shutil.copytree(VALID_PKG, tmpdir / "broken", dirs_exist_ok=True)
        (tmpdir / "broken" / "manifest.json").unlink()
        with pytest.raises(FileNotFoundError, match="Missing manifest.json"):
            load_evidence_package(tmpdir / "broken")


def test_missing_timeline():
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        shutil.copytree(VALID_PKG, tmpdir / "broken", dirs_exist_ok=True)
        (tmpdir / "broken" / "timeline.json").unlink()
        with pytest.raises(FileNotFoundError, match="Missing timeline.json"):
            load_evidence_package(tmpdir / "broken")


def test_invalid_manifest_json():
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        (tmpdir / "broken").mkdir()
        (tmpdir / "broken" / "manifest.json").write_text("not valid json", encoding="utf-8")
        (tmpdir / "broken" / "timeline.json").write_text("[]", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid JSON in manifest.json"):
            load_evidence_package(tmpdir / "broken")


def test_invalid_timeline_json():
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        (tmpdir / "broken").mkdir()
        (tmpdir / "broken" / "manifest.json").write_text(
            json.dumps({"source": "test", "schema_version": "v1", "run_id": "r1"}), encoding="utf-8"
        )
        (tmpdir / "broken" / "timeline.json").write_text("not valid json", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid JSON in timeline.json"):
            load_evidence_package(tmpdir / "broken")
