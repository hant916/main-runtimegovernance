from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO / "examples" / "reference_apps" / "fixtures" / "clarify_timeline_v0.json"

sys.path.insert(0, str(REPO / "src"))

from ailuros.adapters.clarify_timeline_contract import (  # noqa: E402
    REQUIRED_EVENT_TYPES,
    REQUIRED_SCHEMA_VERSION,
    validate_clarify_timeline,
)


def main() -> int:
    if not FIXTURE_PATH.is_file():
        print(f"FAIL: fixture not found: {FIXTURE_PATH}")
        return 1

    try:
        timeline = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"FAIL: invalid JSON in fixture: {exc}")
        return 1

    if not isinstance(timeline, dict):
        print("FAIL: fixture root must be a JSON object with schema_version and events")
        return 1

    events = timeline.get("events", [])
    print(f"loaded {len(events)} event(s) from clarify_timeline_v0.json")

    errors = validate_clarify_timeline(timeline)
    if errors:
        print(f"FAIL: {len(errors)} contract validation error(s):")
        for err in errors:
            print(f"  {err}")
        return 1

    print("OK: clarify timeline v0 fixture validates against evidence contract")
    print(f"  schema_version: {REQUIRED_SCHEMA_VERSION}")
    print(f"  required event_types: {sorted(REQUIRED_EVENT_TYPES)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
