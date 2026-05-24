from __future__ import annotations

from pathlib import Path

from ailuros.errors import AilurosDataCorruptionError, AilurosNotFoundError
from ailuros.models import RuntimeEvent
from ailuros.storage import SQLiteStorage


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
