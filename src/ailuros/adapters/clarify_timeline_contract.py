from __future__ import annotations

from typing import Any

REQUIRED_SCHEMA_VERSION = "ailuros.timeline.v0"
REQUIRED_EVENT_TYPES = {
    "INPUT_CLASSIFIED",
    "LLM_REQUEST",
    "LLM_RESPONSE",
    "EVALUATION_RESULT",
    "OUTPUT_GENERATED",
    "RUN_COMPLETED",
}


def validate_clarify_timeline(timeline: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if timeline.get("schema_version") != REQUIRED_SCHEMA_VERSION:
        errors.append(
            f"invalid schema_version {timeline.get('schema_version')!r}, "
            f"expected {REQUIRED_SCHEMA_VERSION!r}"
        )

    events = timeline.get("events")
    if not isinstance(events, list) or not events:
        errors.append("events must be a non-empty array")
        return errors

    seen_event_types: set[str] = set()
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            errors.append(f"event[{index}] must be an object")
            continue

        event_type = event.get("event")
        if not isinstance(event_type, str) or not event_type:
            errors.append(f"event[{index}] missing event")
        else:
            seen_event_types.add(event_type)

        for field in ("run_id", "timestamp"):
            value = event.get(field)
            if not isinstance(value, str) or not value:
                errors.append(f"event[{index}] missing {field}")

    for event_type in sorted(REQUIRED_EVENT_TYPES - seen_event_types):
        errors.append(f"missing required event {event_type!r}")

    return errors
