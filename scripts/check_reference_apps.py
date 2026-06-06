"""Reference-app readiness gate. Exit 0 if all reference-app checks pass."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(REPO / "src"))

from ailuros.adapters.clarify_timeline_contract import (  # noqa: E402
    REQUIRED_EVENT_TYPES,
    REQUIRED_SCHEMA_VERSION,
    validate_clarify_timeline,
)

FIXTURE_PATH = REPO / "examples" / "reference_apps" / "fixtures" / "clarify_timeline_v0.json"

CHECKS_PASSED: list[str] = []
CHECKS_FAILED: list[str] = []


def ok(msg: str) -> None:
    CHECKS_PASSED.append(msg)
    print(f"  ok  {msg}")


def fail(msg: str) -> None:
    CHECKS_FAILED.append(msg)
    print(f"FAIL  {msg}")


def main() -> int:
    print("Ailuros reference-app readiness gate")
    print("=" * 40)

    if FIXTURE_PATH.is_file():
        ok("Clarify timeline v0 golden fixture exists")
    else:
        fail("Clarify timeline v0 golden fixture missing")
        print("=" * 40)
        print(f"Passed: {len(CHECKS_PASSED)}  Failed: {len(CHECKS_FAILED)}")
        return 1

    contract_path = REPO / "src" / "ailuros" / "adapters" / "clarify_timeline_contract.py"
    if contract_path.is_file():
        ok("Clarify timeline contract validator exists")
    else:
        fail("Clarify timeline contract validator missing")
        print("=" * 40)
        print(f"Passed: {len(CHECKS_PASSED)}  Failed: {len(CHECKS_FAILED)}")
        return 1

    try:
        timeline = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in fixture: {exc}")
        print("=" * 40)
        print(f"Passed: {len(CHECKS_PASSED)}  Failed: {len(CHECKS_FAILED)}")
        return 1

    events = timeline.get("events", [])
    print(f"  loaded {len(events)} event(s) from clarify_timeline_v0.json")

    errors = validate_clarify_timeline(timeline)
    if errors:
        fail(f"{len(errors)} contract validation error(s):")
        for err in errors:
            fail(f"  {err}")
    else:
        ok("Clarify timeline v0 fixture validates against evidence contract")
        print(f"  schema_version: {REQUIRED_SCHEMA_VERSION}")
        print(f"  required event_types: {sorted(REQUIRED_EVENT_TYPES)}")

    print("=" * 40)
    print(f"Passed: {len(CHECKS_PASSED)}  Failed: {len(CHECKS_FAILED)}")

    if CHECKS_FAILED:
        print("\nFailed checks:")
        for msg in CHECKS_FAILED:
            print(f"  - {msg}")
        return 1

    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
