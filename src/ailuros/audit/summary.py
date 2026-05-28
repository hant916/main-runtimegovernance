from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ailuros.models import RuntimeEvent, RuntimeEventType
from ailuros.storage.sqlite_storage import SQLiteStorage

UNKNOWN = "unknown"
ABSENT = "absent"


@dataclass(frozen=True)
class AuditSummary:
    decision: str
    reason: str
    tool: str
    path_validation: str


def build_audit_summary(events: list[RuntimeEvent]) -> AuditSummary:
    decision = UNKNOWN
    reason = UNKNOWN
    tool = UNKNOWN
    path_validation = ABSENT
    latest_tool = UNKNOWN

    for event in events:
        payload = event.payload
        if event.event_type is RuntimeEventType.TOOL_CALL_REQUESTED:
            latest_tool = _string_field(payload, "tool_name")
        elif event.event_type is RuntimeEventType.PATH_VALIDATION_RESULT:
            path_validation = _path_validation(payload)
        elif event.event_type is RuntimeEventType.GOVERNANCE_DECISION:
            decision = _string_field(payload, "decision")
            reason = _string_field(payload, "reason")
            tool = _string_field(payload, "tool_name")
            if tool == UNKNOWN:
                tool = latest_tool
        elif event.event_type is RuntimeEventType.TOOL_CALL_BLOCKED and tool == UNKNOWN:
            tool = _string_field(payload, "tool_name")

    return AuditSummary(
        decision=decision,
        reason=reason,
        tool=tool,
        path_validation=path_validation,
    )


def _string_field(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    return value if isinstance(value, str) and value else UNKNOWN


def _path_validation(payload: dict[str, Any]) -> str:
    value = payload.get("valid")
    if isinstance(value, bool):
        return "valid" if value else "invalid"
    return UNKNOWN


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    status: str
    event_count: int
    decision_counts: dict[str, int]
    blocked_count: int
    review_count: int
    started_at: str | None = None
    completed_at: str | None = None
    metadata_version: str = "1"


def build_run_summary(storage: SQLiteStorage, run_id: str) -> RunSummary:
    run = storage.get_run(run_id)
    events = storage.list_events(run_id)

    decision_counts: dict[str, int] = {}
    started_at: str | None = None
    completed_at: str | None = None

    for event in events:
        if event.event_type is RuntimeEventType.GOVERNANCE_DECISION:
            decision = event.payload.get("decision")
            if isinstance(decision, str):
                decision_counts[decision] = decision_counts.get(decision, 0) + 1
        elif event.event_type is RuntimeEventType.RUN_STARTED:
            started_at = event.timestamp.isoformat()
        elif event.event_type is RuntimeEventType.RUN_COMPLETED:
            completed_at = event.timestamp.isoformat()

    return RunSummary(
        run_id=run.run_id,
        status=run.status.value,
        event_count=len(events),
        decision_counts=decision_counts,
        blocked_count=decision_counts.get("block", 0),
        review_count=decision_counts.get("require_review", 0),
        started_at=started_at,
        completed_at=completed_at,
    )
