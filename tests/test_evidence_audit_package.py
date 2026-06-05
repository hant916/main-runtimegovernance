from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ailuros import EvidenceRecord
from ailuros.audit.package_export import export_audit_package
from ailuros.evidence.ingest import ingest_evidence
from ailuros.models import Environment, Run, RunStatus
from ailuros.storage import SQLiteStorage


def _make_run(storage: SQLiteStorage, run_id: str) -> Run:
    now = datetime.now(UTC)
    run = Run(
        run_id=run_id,
        agent_id="agent-1",
        environment=Environment.DEVELOPMENT,
        status=RunStatus.RUNNING,
        input={"prompt": "test"},
        created_at=now,
        updated_at=now,
    )
    storage.create_run(run)
    return run


def _make_evidence_record(**kwargs: object) -> EvidenceRecord:
    base: dict = {
        "version": "1.0.0",
        "run_id": kwargs.get("run_id", "run-eap-001"),
        "event_type": "navigation",
        "payload": {"url": "https://example.com", "title": "Test"},
        "timestamp": datetime.now(tz=UTC),
    }
    base.update(kwargs)
    return EvidenceRecord(**base)


class TestAuditPackageEvidenceSection:
    def test_package_has_evidence_key(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-eap-001")

        package = export_audit_package(storage, "run-eap-001")

        assert "evidence" in package
        assert isinstance(package["evidence"], list)

    def test_evidence_empty_when_no_evidence_events(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-eap-002")

        package = export_audit_package(storage, "run-eap-002")

        assert package["evidence"] == []

    def test_evidence_includes_single_evidence_event(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-eap-003")
        record = _make_evidence_record(run_id="run-eap-003")
        ingest_evidence(storage, record)

        package = export_audit_package(storage, "run-eap-003")

        assert len(package["evidence"]) == 1

    def test_evidence_entries_have_required_fields(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-eap-004")
        record = _make_evidence_record(run_id="run-eap-004")
        ingest_evidence(storage, record)

        package = export_audit_package(storage, "run-eap-004")
        entry = package["evidence"][0]

        assert "event_id" in entry
        assert "run_id" in entry
        assert "event_type" in entry
        assert "timestamp" in entry
        assert "evidence" in entry

    def test_evidence_has_opaque_payload_in_sub_object(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-eap-005")
        record = _make_evidence_record(
            run_id="run-eap-005",
            event_type="custom_check",
            payload={"url": "https://a.com", "nested": {"deep": 99}, "items": [1, 2]},
        )
        ingest_evidence(storage, record)

        package = export_audit_package(storage, "run-eap-005")
        evidence = package["evidence"][0]["evidence"]

        assert evidence["version"] == "1.0.0"
        assert evidence["event_type"] == "custom_check"
        expected = {"url": "https://a.com", "nested": {"deep": 99}, "items": [1, 2]}
        assert evidence["payload"] == expected

    def test_evidence_ordered_by_sequence(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-eap-006")

        for i in range(3):
            record = _make_evidence_record(
                run_id="run-eap-006",
                event_type=f"event_{i}",
                payload={"index": i},
                timestamp=datetime(2025, 1, 15, 10, 30, i, tzinfo=UTC),
            )
            ingest_evidence(storage, record)

        package = export_audit_package(storage, "run-eap-006")
        sequences = [e["sequence"] for e in package["evidence"]]
        assert sequences == sorted(sequences)

    def test_evidence_export_is_read_only(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-eap-007")
        record = _make_evidence_record(run_id="run-eap-007")
        ingest_evidence(storage, record)

        events_before = storage.list_events("run-eap-007")
        export_audit_package(storage, "run-eap-007")
        events_after = storage.list_events("run-eap-007")

        assert len(events_before) == len(events_after)
        assert events_before[0].event_id == events_after[0].event_id
