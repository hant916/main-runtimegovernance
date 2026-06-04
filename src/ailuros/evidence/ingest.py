from __future__ import annotations

from ailuros.models import EvidenceRecord, RuntimeEvent, RuntimeEventType
from ailuros.runtime.ids import new_event_id
from ailuros.storage import SQLiteStorage


def ingest_evidence(storage: SQLiteStorage, record: EvidenceRecord) -> RuntimeEvent:
    event = RuntimeEvent(
        event_id=new_event_id(),
        run_id=record.run_id,
        event_type=RuntimeEventType.EVIDENCE,
        timestamp=record.timestamp,
        payload={
            "version": record.version,
            "event_type": record.event_type,
            "payload": record.payload,
        },
    )
    return storage.append_event(event)
