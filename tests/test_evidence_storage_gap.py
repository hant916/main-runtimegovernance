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
        "run_id": "run-gap-001",
        "event_type": "navigation",
        "payload": {"url": "https://example.com", "title": "Test Page"},
        "timestamp": datetime.now(tz=UTC),
    }
    base.update(kwargs)
    return EvidenceRecord(**base)


class TestEvidenceStorageNoGap:
    def test_evidence_persists_via_generic_events_table(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-gap-001")
        record = _make_record()
        event = ingest_evidence(storage, record)

        assert event.event_type == RuntimeEventType.EVIDENCE
        assert event.event_id.startswith("evt_")
        assert event.run_id == "run-gap-001"
        assert event.sequence is not None
        assert event.sequence >= 1

    def test_evidence_readable_via_list_events(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-gap-001")
        record = _make_record(payload={"key": "gap-test", "nested": {"val": 42}})
        ingested = ingest_evidence(storage, record)

        events = storage.list_events("run-gap-001")
        evidence_events = [e for e in events if e.event_type == RuntimeEventType.EVIDENCE]
        assert len(evidence_events) == 1
        read_back = evidence_events[0]
        assert read_back.event_id == ingested.event_id
        assert read_back.run_id == "run-gap-001"
        assert read_back.sequence == ingested.sequence

    def test_evidence_payload_opaque_roundtrip(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-gap-001")
        payload = {"domain_event": "user.clicked", "meta": {"page": "/home", "duration_ms": 342}}
        record = _make_record(event_type="custom_click_event", payload=payload)

        event = ingest_evidence(storage, record)

        assert event.payload["version"] == "1.0.0"
        assert event.payload["event_type"] == "custom_click_event"
        assert event.payload["payload"] == payload
        assert event.payload["payload"]["domain_event"] == "user.clicked"
        assert event.payload["payload"]["meta"]["duration_ms"] == 342

    def test_evidence_coexists_with_non_evidence_timeline_events(
        self, tmp_path: Path
    ) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-gap-001")

        from ailuros.models import RuntimeEvent, RuntimeEventType
        from ailuros.runtime.ids import new_event_id

        non_evidence = RuntimeEvent(
            event_id=new_event_id(),
            run_id="run-gap-001",
            event_type=RuntimeEventType.RUN_STARTED,
            timestamp=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
            payload={"agent": "test-agent"},
        )
        storage.append_event(non_evidence)

        evidence = ingest_evidence(
            storage,
            _make_record(
                run_id="run-gap-001",
                timestamp=datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC),
            ),
        )

        all_events = storage.list_events("run-gap-001")
        assert len(all_events) == 2

        non_evidence_list = [e for e in all_events if e.event_type == RuntimeEventType.RUN_STARTED]
        assert len(non_evidence_list) == 1
        assert non_evidence_list[0].payload["agent"] == "test-agent"

        evidence_list = [e for e in all_events if e.event_type == RuntimeEventType.EVIDENCE]
        assert len(evidence_list) == 1
        assert evidence_list[0].event_id == evidence.event_id

    def test_multiple_evidence_events_monotonic_sequence(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-gap-001")

        events = []
        for i in range(5):
            record = _make_record(
                run_id="run-gap-001",
                event_type=f"domain_event_{i}",
                payload={"seq_index": i},
                timestamp=datetime(2025, 1, 15, 10, 30, i, tzinfo=UTC),
            )
            events.append(ingest_evidence(storage, record))

        all_events = storage.list_events("run-gap-001")
        evidence_events = [e for e in all_events if e.event_type == RuntimeEventType.EVIDENCE]
        assert len(evidence_events) == 5
        sequences = [e.sequence for e in evidence_events]
        assert sequences == sorted(sequences)
        assert len(set(sequences)) == 5

    def test_no_dedicated_evidence_table_required(self, tmp_path: Path) -> None:
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run(storage, "run-gap-001")

        ingest_evidence(storage, _make_record(run_id="run-gap-001"))

        events = storage.list_events("run-gap-001")
        assert len(events) == 1
        assert events[0].event_type == RuntimeEventType.EVIDENCE

        assert hasattr(storage, "append_event")
        assert hasattr(storage, "list_events")
        assert not hasattr(storage, "append_evidence")
