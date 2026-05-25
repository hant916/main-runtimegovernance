from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ailuros.models import RuntimeEvent, RuntimeEventType

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
