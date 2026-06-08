from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCE_PATH = REPO / "examples" / "ailuros" / "clarify_timeline_v0.sample.json"
TARGET_PATH = REPO / "examples" / "reference_apps" / "fixtures" / "clarify_timeline_v0.json"

sys.path.insert(0, str(REPO / "src"))

from ailuros.adapters.clarify_timeline_contract import (  # noqa: E402
    REQUIRED_EVENT_TYPES,
    REQUIRED_SCHEMA_VERSION,
    validate_clarify_timeline,
)

EXIT_OK = 0
EXIT_FAIL = 1


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"FAIL: invalid JSON in {path}: {exc}")
        sys.exit(EXIT_FAIL)
    if not isinstance(data, dict):
        print(f"FAIL: {path} root must be a JSON object")
        sys.exit(EXIT_FAIL)
    return data


def validate_file(label: str, path: Path) -> dict:
    print(f"--- {label}: {path}")
    if not path.is_file():
        print(f"FAIL: {label} not found: {path}")
        sys.exit(EXIT_FAIL)

    timeline = load_json(path)
    events = timeline.get("events", [])
    print(f"  loaded {len(events)} event(s)")

    errors = validate_clarify_timeline(timeline)
    if errors:
        print(f"FAIL: {label} has {len(errors)} contract validation error(s):")
        for err in errors:
            print(f"  {err}")
        sys.exit(EXIT_FAIL)

    print(f"PASS: {label} validates against contract")
    print(f"  schema_version: {REQUIRED_SCHEMA_VERSION}")
    print(f"  required event_types: {sorted(REQUIRED_EVENT_TYPES)}")
    return timeline


def compare_timelines(source: dict, target: dict) -> None:
    print("--- semantic equality check")
    source_run_id = source.get("run_id")
    target_run_id = target.get("run_id")

    source_events = source.get("events", [])
    target_events = target.get("events", [])
    source_types = sorted(e.get("event") for e in source_events if isinstance(e, dict))
    target_types = sorted(e.get("event") for e in target_events if isinstance(e, dict))

    if source_run_id != target_run_id:
        print(f"FAIL: run_id mismatch: source={source_run_id!r} target={target_run_id!r}")
        sys.exit(EXIT_FAIL)

    if source_types != target_types:
        print(f"FAIL: event type mismatch: source={source_types} target={target_types}")
        sys.exit(EXIT_FAIL)

    if len(source_events) != len(target_events):
        print(
            f"FAIL: event count mismatch: "
            f"source={len(source_events)} target={len(target_events)}"
        )
        sys.exit(EXIT_FAIL)

    fields_to_compare = ("event", "run_id", "timestamp")
    for idx, (se, te) in enumerate(zip(source_events, target_events, strict=False)):
        for field in fields_to_compare:
            sv = se.get(field)
            tv = te.get(field)
            if sv != tv:
                print(
                    f"FAIL: event[{idx}].{field} mismatch: "
                    f"source={sv!r} target={tv!r}"
                )
                sys.exit(EXIT_FAIL)

    print(f"PASS: source and target timelines are semantically equal "
          f"({len(source_events)} events, {source_run_id!r})")


def main() -> int:
    print("C-008 Clarify Handoff Validation")
    print(f"  REQUIRED_SCHEMA_VERSION: {REQUIRED_SCHEMA_VERSION}")
    print(f"  REQUIRED_EVENT_TYPES: {sorted(REQUIRED_EVENT_TYPES)}")
    print()

    source = validate_file("source (canonical sample)", SOURCE_PATH)
    print()
    target = validate_file("target (C-008 destination)", TARGET_PATH)
    print()
    compare_timelines(source, target)
    print()
    print("C-008 ACCEPT: Clarify handoff evidence present and valid")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
