from __future__ import annotations

from pathlib import Path
from typing import Any

from ailuros.errors import AilurosDataCorruptionError, AilurosNotFoundError
from ailuros.models import RuntimeEvent, RuntimeEventType
from ailuros.storage import SQLiteStorage

DECISION_FIELDS = {"decision", "allowed", "reason", "severity", "matched_policy_ids"}
TOOL_FIELDS = {"tool_name", "arguments", "result"}


class ReplayService:
    def __init__(self, storage: SQLiteStorage | str | Path) -> None:
        if isinstance(storage, SQLiteStorage):
            self._storage = storage
        else:
            self._storage = SQLiteStorage(storage)

    def load_run(self, run_id: str) -> list[RuntimeEvent]:
        try:
            events = self._storage.list_events(run_id)
        except AilurosDataCorruptionError as exc:
            raise AilurosDataCorruptionError(
                f"corrupt replay event payload for run_id={run_id} "
                "at events.payload_json"
            ) from exc

        if not events:
            raise AilurosNotFoundError(f"replay timeline not found for run_id={run_id}")
        return events

    def build_timeline(self, run_id: str) -> list[dict[str, Any]]:
        events = self.load_run(run_id)
        timeline: list[dict[str, Any]] = []
        for event in events:
            entry: dict[str, Any] = {
                "sequence_number": event.sequence,
                "event_type": event.event_type.value,
                "event_id": event.event_id,
                "timestamp": event.timestamp.isoformat(),
                "step_id": event.step_id,
            }
            metadata = _extract_metadata(event)
            if metadata:
                entry["metadata"] = metadata
            timeline.append(entry)
        return timeline


def _extract_metadata(event: RuntimeEvent) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if event.event_type is RuntimeEventType.GOVERNANCE_DECISION:
        for field in DECISION_FIELDS:
            if field in event.payload:
                metadata[field] = event.payload[field]
    for field in TOOL_FIELDS:
        if field in event.payload:
            metadata[field] = event.payload[field]
    return metadata
