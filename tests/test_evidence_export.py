import json
from datetime import UTC, datetime
from pathlib import Path

from ailuros import EvidenceRecord
from ailuros.evidence.export import (
    export_evidence,
    export_evidence_json,
    export_evidence_jsonl,
)
from ailuros.evidence.ingest import ingest_evidence
from ailuros.models import Environment, Run, RunStatus
from ailuros.storage import SQLiteStorage


def _make_run(storage: SQLiteStorage, run_id: str) -> Run:
    now = datetime.now(UTC)
    run = Run(
        run_id=run_id,
        agent_id="agent",
        environment=Environment.DEVELOPMENT,
        status=RunStatus.RUNNING,
        input={"prompt": "test"},
        created_at=now,
        updated_at=now,
    )
    storage.create_run(run)
    return run


def _make_record(**kwargs) -> EvidenceRecord:
    base: dict = {
        "version": "1.0.0",
        "run_id": "run-export-001",
        "event_type": "navigation",
        "payload": {"url": "https://example.com", "title": "Test Page"},
        "timestamp": datetime.now(tz=UTC),
    }
    base.update(kwargs)
    return EvidenceRecord(**base)


class TestEvidenceExport:
    def test_export_empty_when_no_evidence(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-export-001")

        records = export_evidence(storage, "run-export-001")
        assert records == []

    def test_export_preserves_event_identity(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-export-001")
        record = _make_record()
        event = ingest_evidence(storage, record)

        records = export_evidence(storage, "run-export-001")
        assert len(records) == 1
        assert records[0]["event_id"] == event.event_id

    def test_export_preserves_sequence_ordering(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-export-001")

        for i in range(5):
            record = _make_record(
                run_id="run-export-001",
                event_type=f"event_{i}",
                payload={"index": i},
                timestamp=datetime(2025, 1, 15, 10, 30, i, tzinfo=UTC),
            )
            ingest_evidence(storage, record)

        records = export_evidence(storage, "run-export-001")
        assert len(records) == 5
        sequences = [r["sequence"] for r in records]
        assert sequences == sorted(sequences)
        assert len(set(sequences)) == 5

    def test_export_preserves_timestamps(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-export-001")
        ts = datetime(2025, 3, 15, 14, 0, 0, tzinfo=UTC)
        record = _make_record(timestamp=ts)
        ingest_evidence(storage, record)

        records = export_evidence(storage, "run-export-001")
        assert records[0]["timestamp"] == ts.isoformat()

    def test_export_preserves_evidence_payload(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-export-001")
        payload = {"url": "https://a.com", "nested": {"deep": 99}, "items": [1, 2]}
        record = _make_record(payload=payload, event_type="custom_check")
        ingest_evidence(storage, record)

        records = export_evidence(storage, "run-export-001")
        evidence = records[0]["evidence"]
        assert evidence["version"] == "1.0.0"
        assert evidence["event_type"] == "custom_check"
        assert evidence["payload"] == payload

    def test_export_is_read_only(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-export-001")
        record = _make_record()
        ingest_evidence(storage, record)

        events_before = storage.list_events("run-export-001")
        export_evidence(storage, "run-export-001")
        events_after = storage.list_events("run-export-001")

        assert len(events_before) == len(events_after)
        assert events_before[0].event_id == events_after[0].event_id


class TestEvidenceExportJSON:
    def test_json_output_is_valid_and_parsable(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-export-001")
        record = _make_record()
        ingest_evidence(storage, record)

        output = export_evidence_json(storage, "run-export-001")
        parsed = json.loads(output)
        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert parsed[0]["event_id"].startswith("evt_")

    def test_json_output_handles_multiple_events(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-export-001")
        for i in range(3):
            record = _make_record(
                run_id="run-export-001",
                event_type=f"event_{i}",
                payload={"index": i},
                timestamp=datetime(2025, 1, 15, 10, 30, i, tzinfo=UTC),
            )
            ingest_evidence(storage, record)

        output = export_evidence_json(storage, "run-export-001")
        parsed = json.loads(output)
        assert len(parsed) == 3


class TestEvidenceExportJSONL:
    def test_jsonl_output_has_correct_line_count(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-export-001")
        for i in range(3):
            record = _make_record(
                run_id="run-export-001",
                event_type=f"event_{i}",
                payload={"index": i},
                timestamp=datetime(2025, 1, 15, 10, 30, i, tzinfo=UTC),
            )
            ingest_evidence(storage, record)

        output = export_evidence_jsonl(storage, "run-export-001")
        lines = output.splitlines()
        assert len(lines) == 3

    def test_jsonl_each_line_is_parsable_json(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-export-001")
        record = _make_record()
        ingest_evidence(storage, record)

        output = export_evidence_jsonl(storage, "run-export-001")
        lines = output.splitlines()
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["event_id"].startswith("evt_")

    def test_jsonl_empty_when_no_evidence(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-export-001")

        output = export_evidence_jsonl(storage, "run-export-001")
        assert output == ""


class TestEvidenceExportFiltersNonEvidence:
    def test_export_excludes_non_evidence_events(self, tmp_path: Path) -> None:
        from ailuros.models import RuntimeEvent, RuntimeEventType
        from ailuros.runtime.ids import new_event_id

        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-export-001")

        record = _make_record()
        ingest_evidence(storage, record)

        non_evidence = RuntimeEvent(
            event_id=new_event_id(),
            run_id="run-export-001",
            event_type=RuntimeEventType.RUN_STARTED,
            timestamp=datetime.now(UTC),
            payload={},
        )
        storage.append_event(non_evidence)

        records = export_evidence(storage, "run-export-001")
        assert len(records) == 1
        assert records[0]["event_type"] == "evidence"
