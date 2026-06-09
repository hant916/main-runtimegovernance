from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO / "tests" / "fixtures" / "clarify" / "clarify_timeline_v0.sample.json"

REQUIRED_SCHEMA_VERSION = "ailuros.timeline.v0"
REQUIRED_EVENT_TYPES: frozenset[str] = frozenset({
    "INPUT_CLASSIFIED",
    "LLM_REQUEST",
    "LLM_RESPONSE",
    "EVALUATION_RESULT",
    "OUTPUT_GENERATED",
    "RUN_COMPLETED",
})

ISO_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$"
)

EXIT_OK = 0
EXIT_FAIL = 1


def _fmt_errors(errors: list[str]) -> str:
    lines = [f"  - {e}" for e in errors]
    return "\n".join(lines)


def validate_timeline_contract(data: dict) -> list[str]:
    errors: list[str] = []

    if data.get("schema_version") != REQUIRED_SCHEMA_VERSION:
        errors.append(
            f"schema_version: expected {REQUIRED_SCHEMA_VERSION!r}, "
            f"got {data.get('schema_version')!r}"
        )

    source = data.get("producer") or data.get("source")
    if source is not None and not isinstance(source, str):
        errors.append("producer/source metadata must be a string if present")

    run_id = data.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        errors.append("run_id must be a non-empty string")

    created_at = data.get("created_at")
    if not isinstance(created_at, str) or not created_at:
        errors.append("created_at must be a non-empty string")

    events = data.get("events")
    if not isinstance(events, list):
        errors.append("events must be an array")
        return errors

    if not events:
        errors.append("events must be a non-empty array")
        return errors

    seen_event_types: set[str] = set()

    for idx, event in enumerate(events):
        if not isinstance(event, dict):
            errors.append(f"events[{idx}] must be an object")
            continue

        event_type = event.get("event")
        if not isinstance(event_type, str) or not event_type:
            errors.append(f"events[{idx}].event must be a non-empty string")
        else:
            seen_event_types.add(event_type)

        eid = event.get("id")
        if eid is not None and (not isinstance(eid, str) or not eid):
            errors.append(f"events[{idx}].id must be a non-empty string if present")

        e_run_id = event.get("run_id")
        if not isinstance(e_run_id, str) or not e_run_id:
            errors.append(f"events[{idx}].run_id must be a non-empty string")

        ts = event.get("timestamp")
        if not isinstance(ts, str) or not ts:
            errors.append(f"events[{idx}].timestamp must be a non-empty string")
        elif not ISO_TIMESTAMP_RE.match(ts):
            errors.append(f"events[{idx}].timestamp {ts!r} is not ISO 8601 UTC")

        payload = event.get("metadata") or event.get("data")
        if payload is not None and not isinstance(payload, dict):
            errors.append(
                f"events[{idx}] payload (metadata/data) must be an object if present"
            )

    missing = sorted(REQUIRED_EVENT_TYPES - seen_event_types)
    for event_type in missing:
        errors.append(f"missing required event type {event_type!r}")

    return errors


def main() -> int:
    print("=== Clarify Timeline Contract Validator (offline) ===")
    print(f"Fixture: {FIXTURE_PATH}")

    if not FIXTURE_PATH.is_file():
        print(f"FAIL: fixture not found at {FIXTURE_PATH}")
        return EXIT_FAIL

    try:
        data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"FAIL: invalid JSON in fixture: {exc}")
        return EXIT_FAIL

    if not isinstance(data, dict):
        print("FAIL: fixture root must be a JSON object")
        return EXIT_FAIL

    events = data.get("events", [])
    print(f"  events loaded: {len(events)}")
    print()

    errors = validate_timeline_contract(data)

    if errors:
        print(f"FAIL: {len(errors)} contract violation(s):")
        print(_fmt_errors(errors))
        return EXIT_FAIL

    print("PASS: all contract checks passed")
    print(f"  schema_version: {REQUIRED_SCHEMA_VERSION}")
    print(f"  required event types: {sorted(REQUIRED_EVENT_TYPES)}")
    print(f"  events: {len(events)}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
