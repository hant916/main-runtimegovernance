from __future__ import annotations

import json
from typing import Any

from ailuros.storage import SQLiteStorage

_EVIDENCE_EVENT_TYPES = {"evidence", "external_evidence"}


def export_evidence(storage: SQLiteStorage, run_id: str) -> list[dict[str, Any]]:
    events = storage.list_events(run_id)
    evidence_events = [
        e for e in events if e.event_type.value in _EVIDENCE_EVENT_TYPES
    ]
    evidence_events.sort(key=lambda e: e.sequence or 0)
    return [
        {
            "event_id": e.event_id,
            "run_id": e.run_id,
            "event_type": e.event_type.value,
            "timestamp": e.timestamp.isoformat(),
            "sequence": e.sequence,
            "evidence": e.payload,
        }
        for e in evidence_events
    ]


def export_evidence_json(storage: SQLiteStorage, run_id: str) -> str:
    return json.dumps(export_evidence(storage, run_id), indent=2, default=str)


def export_evidence_jsonl(storage: SQLiteStorage, run_id: str) -> str:
    records = export_evidence(storage, run_id)
    return "\n".join(json.dumps(r, default=str) for r in records)
