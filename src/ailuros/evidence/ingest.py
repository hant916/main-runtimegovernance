from __future__ import annotations

from typing import Protocol, runtime_checkable

from ailuros.models import EvidenceRecord, RuntimeEvent, RuntimeEventType
from ailuros.runtime.ids import new_event_id


@runtime_checkable
class EventAppender(Protocol):
    def append_event(self, event: RuntimeEvent) -> RuntimeEvent: ...


def ingest_evidence(storage: EventAppender, record: EvidenceRecord) -> RuntimeEvent:
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
