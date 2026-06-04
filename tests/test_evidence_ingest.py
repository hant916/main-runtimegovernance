from datetime import UTC, datetime
from pathlib import Path

from ailuros import EvidenceRecord, RuntimeEventType
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
        "run_id": "run-test-001",
        "event_type": "navigation",
        "payload": {"url": "https://example.com", "title": "Test Page"},
        "timestamp": datetime.now(tz=UTC),
    }
    base.update(kwargs)
    return EvidenceRecord(**base)


class TestEvidenceIngestTimeline:
    def test_ingest_stores_as_timeline_event(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-test-001")
        record = _make_record()

        event = ingest_evidence(storage, record)

        assert event.event_type == RuntimeEventType.EVIDENCE
        assert event.run_id == "run-test-001"
        assert event.sequence is not None
        assert event.sequence >= 1

    def test_ingested_evidence_visible_via_list_events(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-test-001")
        record = _make_record()

        ingest_evidence(storage, record)
        events = storage.list_events("run-test-001")

        evidence_events = [e for e in events if e.event_type == RuntimeEventType.EVIDENCE]
        assert len(evidence_events) == 1
        assert evidence_events[0].run_id == "run-test-001"

    def test_ingest_preserves_payload_opaquely(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-test-001")
        payload = {"url": "https://a.com", "nested": {"deep": 42}, "items": [1, 2]}
        record = _make_record(payload=payload)

        event = ingest_evidence(storage, record)

        assert event.payload["payload"] == payload
        assert event.payload["version"] == "1.0.0"
        assert event.payload["event_type"] == "navigation"

    def test_ingest_preserves_evidence_timestamp(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-test-001")
        ts = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)
        record = _make_record(timestamp=ts)

        event = ingest_evidence(storage, record)

        assert event.timestamp == ts

    def test_ingest_multiple_evidence_events(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-test-001")

        for i in range(3):
            record = _make_record(
                run_id="run-test-001",
                event_type=f"event_{i}",
                payload={"index": i},
                timestamp=datetime(2025, 1, 15, 10, 30, i, tzinfo=UTC),
            )
            ingest_evidence(storage, record)

        events = storage.list_events("run-test-001")
        evidence_events = [e for e in events if e.event_type == RuntimeEventType.EVIDENCE]
        assert len(evidence_events) == 3
        s0 = evidence_events[0].sequence
        s1 = evidence_events[1].sequence
        s2 = evidence_events[2].sequence
        assert s0 < s1 < s2

    def test_ingest_event_has_unique_event_id(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-test-001")

        event1 = ingest_evidence(storage, _make_record())
        event2 = ingest_evidence(storage, _make_record())

        assert event1.event_id != event2.event_id
        assert event1.event_id.startswith("evt_")


class TestEvidenceIngestBoundaries:
    def test_ingest_with_external_evidence_type(self, tmp_path: Path) -> None:
        from ailuros.models import RuntimeEvent, RuntimeEventType
        from ailuros.runtime.ids import new_event_id

        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-test-001")
        record = _make_record()

        event = RuntimeEvent(
            event_id=new_event_id(),
            run_id=record.run_id,
            event_type=RuntimeEventType.EXTERNAL_EVIDENCE,
            timestamp=record.timestamp,
            payload={
                "version": record.version,
                "event_type": record.event_type,
                "payload": record.payload,
            },
        )
        stored = storage.append_event(event)
        assert stored.event_type == RuntimeEventType.EXTERNAL_EVIDENCE

    def test_ingest_preserves_free_form_event_type(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-test-001")

        record = _make_record(event_type="custom_domain_event_v2")
        event = ingest_evidence(storage, record)

        assert event.payload["event_type"] == "custom_domain_event_v2"

    def test_ingest_preserves_payload_as_arbitrary_dict(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-test-001")

        record = _make_record(payload={"anything": "goes", "domain": "unknown"})
        event = ingest_evidence(storage, record)

        assert event.payload["payload"]["anything"] == "goes"
        assert event.payload["payload"]["domain"] == "unknown"
