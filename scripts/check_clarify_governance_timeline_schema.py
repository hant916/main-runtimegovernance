from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO / "schemas" / "clarify-governance-timeline.schema.json"
FIXTURE_PATH = REPO / "tests" / "fixtures" / "clarify" / "clarify_timeline_v0.sample.json"

EXIT_OK = 0
EXIT_FAIL = 1


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_required_fields(
    data: dict, required: list[str], path: str
) -> list[str]:
    errors: list[str] = []
    for field in required:
        if field not in data:
            errors.append(f"{path}: missing required field {field!r}")
        elif data[field] is None:
            errors.append(f"{path}: required field {field!r} is null")
    return errors


def _validate_type(value, expected: str, path: str) -> list[str]:
    errors: list[str] = []
    if expected == "string":
        if not isinstance(value, str):
            errors.append(f"{path}: expected string, got {type(value).__name__}")
    elif expected == "object":
        if not isinstance(value, dict):
            errors.append(f"{path}: expected object, got {type(value).__name__}")
    elif expected == "array":
        if not isinstance(value, list):
            errors.append(f"{path}: expected array, got {type(value).__name__}")
    return errors


def _validate_property(
    data: dict, field: str, prop: dict, path: str
) -> list[str]:
    errors: list[str] = []
    if field not in data:
        return errors
    value = data[field]
    ptype = prop.get("type")
    if ptype:
        errors.extend(_validate_type(value, ptype, f"{path}.{field}"))
    if ptype == "string" and isinstance(value, str):
        min_len = prop.get("minLength")
        if min_len is not None and len(value) < min_len:
            errors.append(
                f"{path}.{field}: length {len(value)} < minLength {min_len}"
            )
    if ptype == "array" and isinstance(value, list):
        min_items = prop.get("minItems")
        if min_items is not None and len(value) < min_items:
            errors.append(
                f"{path}.{field}: {len(value)} items < minItems {min_items}"
            )
    const_val = prop.get("const")
    if const_val is not None and value != const_val:
        errors.append(
            f"{path}.{field}: expected const {const_val!r}, got {value!r}"
        )
    return errors


def _validate_schema_constraints(data: dict, schema: dict) -> list[str]:
    errors: list[str] = []

    props = schema.get("properties", {})
    required = schema.get("required", [])

    errors.extend(_validate_required_fields(data, required, "root"))
    for field, prop in props.items():
        errors.extend(_validate_property(data, field, prop, "root"))

    events = data.get("events", [])
    events_schema = props.get("events", {})

    if isinstance(events, list) and "items" in events_schema:
        item_schema = events_schema["items"]
        item_required = item_schema.get("required", [])
        item_props = item_schema.get("properties", {})

        for i, event in enumerate(events):
            if not isinstance(event, dict):
                errors.append(f"events[{i}]: expected object, got {type(event).__name__}")
                continue
            p = f"events[{i}]"
            errors.extend(_validate_required_fields(event, item_required, p))
            for field, prop in item_props.items():
                errors.extend(_validate_property(event, field, prop, p))

    return errors


def main() -> int:
    print("=== Clarify Governance Timeline Schema Check ===")
    print(f"Schema:  {SCHEMA_PATH}")
    print(f"Fixture: {FIXTURE_PATH}")

    for p, label in [(SCHEMA_PATH, "Schema"), (FIXTURE_PATH, "Fixture")]:
        if not p.is_file():
            print(f"FAIL: {label} not found at {p}")
            return EXIT_FAIL

    try:
        schema = _load_json(SCHEMA_PATH)
    except json.JSONDecodeError as exc:
        print(f"FAIL: invalid JSON in schema: {exc}")
        return EXIT_FAIL

    try:
        fixture = _load_json(FIXTURE_PATH)
    except json.JSONDecodeError as exc:
        print(f"FAIL: invalid JSON in fixture: {exc}")
        return EXIT_FAIL

    if not isinstance(fixture, dict):
        print("FAIL: fixture root must be a JSON object")
        return EXIT_FAIL

    events = fixture.get("events", [])
    print(f"  events loaded: {len(events)}")
    print()

    errors = _validate_schema_constraints(fixture, schema)

    if errors:
        print(f"FAIL: {len(errors)} schema violation(s):")
        for e in errors:
            print(f"  - {e}")
        return EXIT_FAIL

    print("PASS: fixture conforms to governance timeline schema")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
