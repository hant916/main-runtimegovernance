from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from ailuros.adapters.evidence_package import (
    ImportStatus,
    ingest_evidence_package,
    load_evidence_package,
)
from ailuros.storage.sqlite_storage import SQLiteStorage

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures" / "evidence_package"
VALID_V1 = FIXTURES / "valid-v1"


def _new_storage(tmp_path: Path) -> SQLiteStorage:
    db_path = tmp_path / "test.db"
    storage = SQLiteStorage(db_path)
    storage.init()
    return storage


def _copy_and_load_fixture(tmp_path: Path, fixture: Path = VALID_V1) -> Path:
    dest = tmp_path / "pkg"
    shutil.copytree(fixture, dest)
    return dest


def test_first_import_stores_run_and_events(tmp_path):
    pkg_path = _copy_and_load_fixture(tmp_path)
    storage = _new_storage(tmp_path)
    package = load_evidence_package(pkg_path)

    result = ingest_evidence_package(storage, package)

    assert result.status == ImportStatus.CREATED
    assert result.run_id == "run-v1-001"
    assert result.events_imported == 2
    assert result.events_skipped == 0

    stored_run = storage.get_run("run-v1-001")
    assert stored_run.agent_id == "sample-agent-v1"
    assert stored_run.status == "completed"

    events = storage.list_events("run-v1-001")
    assert len(events) == 2
    assert events[0].event_id == "evt-v1-001"
    assert events[1].event_id == "evt-v1-002"
    assert all(e.event_type.value == "external_evidence" for e in events)


def test_second_identical_import_does_not_increase_counts(tmp_path):
    pkg_path = _copy_and_load_fixture(tmp_path)
    storage = _new_storage(tmp_path)
    package = load_evidence_package(pkg_path)

    first = ingest_evidence_package(storage, package)
    assert first.status == ImportStatus.CREATED
    assert first.events_imported == 2

    second = ingest_evidence_package(storage, package)
    assert second.status == ImportStatus.ALREADY_PRESENT
    assert second.events_imported == 0
    assert second.events_skipped == 2

    events = storage.list_events("run-v1-001")
    assert len(events) == 2


def test_changed_same_run_package_produces_conflict(tmp_path):
    pkg_path = _copy_and_load_fixture(tmp_path)
    storage = _new_storage(tmp_path)
    package = load_evidence_package(pkg_path)

    first = ingest_evidence_package(storage, package)
    assert first.status == ImportStatus.CREATED

    timeline = json.loads((pkg_path / "timeline.json").read_text(encoding="utf-8"))
    timeline["events"][0]["payload"] = {"input": "changed payload"}
    (pkg_path / "timeline.json").write_text(json.dumps(timeline), encoding="utf-8")

    changed_package = load_evidence_package(pkg_path)
    result = ingest_evidence_package(storage, changed_package)
    assert result.status == ImportStatus.CONFLICT
    assert result.run_id == "run-v1-001"


def test_import_preserves_run_metadata(tmp_path):
    pkg_path = _copy_and_load_fixture(tmp_path)
    storage = _new_storage(tmp_path)
    package = load_evidence_package(pkg_path)

    ingest_evidence_package(storage, package)
    stored_run = storage.get_run("run-v1-001")
    assert stored_run.metadata.get("imported_from_package") is True
    assert stored_run.metadata.get("source") == "sample-agent-v1"
    assert stored_run.metadata.get("schema_version") == "ailuros.timeline.v1"


def test_import_result_includes_source_digest(tmp_path):
    from ailuros.core.evidence import EvidencePackage, PackageMetadata

    storage = _new_storage(tmp_path)
    package = EvidencePackage(
        source="test-source",
        schema_version="ailuros.timeline.v1",
        run_id="run-digest-001",
        pkg_metadata=PackageMetadata(source_digest="sha256:abc123"),
    )
    result = ingest_evidence_package(storage, package)
    assert result.source_digest == "sha256:abc123"

    stored_run = storage.get_run("run-digest-001")
    assert stored_run.metadata.get("imported_from_package") is True
