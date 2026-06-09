from __future__ import annotations

import json
from pathlib import Path

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "fixtures"
    / "clarify"
    / "clarify_timeline_v0.sample.json"
)
SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "schemas"
    / "clarify-governance-timeline.schema.json"
)

REQUIRED_EVENT_TYPES: frozenset[str] = frozenset({
    "INPUT_CLASSIFIED",
    "LLM_REQUEST",
    "LLM_RESPONSE",
    "EVALUATION_RESULT",
    "OUTPUT_GENERATED",
    "RUN_COMPLETED",
})


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validate_required_fields(
    data: dict, required: list[str], path: str
) -> list[str]:
    errors: list[str] = []
    for field in required:
        if field not in data or data[field] is None:
            errors.append(f"{path}: missing required field {field!r}")
    return errors


def _validate_type(value, expected: str, path: str) -> list[str]:
    errors: list[str] = []
    if expected == "string" and not isinstance(value, str):
        errors.append(f"{path}: expected string, got {type(value).__name__}")
    elif expected == "object" and not isinstance(value, dict):
        errors.append(f"{path}: expected object, got {type(value).__name__}")
    elif expected == "array" and not isinstance(value, list):
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


def validate_schema_constraints(data: dict, schema: dict) -> list[str]:
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
                errors.append(
                    f"events[{i}]: expected object, got {type(event).__name__}"
                )
                continue
            p = f"events[{i}]"
            errors.extend(_validate_required_fields(event, item_required, p))
            for field, prop in item_props.items():
                errors.extend(_validate_property(event, field, prop, p))

    return errors


def _validate_required_event_types(events: list) -> list[str]:
    seen: set[str] = set()
    for event in events:
        if isinstance(event, dict):
            et = event.get("event")
            if isinstance(et, str):
                seen.add(et)
    missing = sorted(REQUIRED_EVENT_TYPES - seen)
    return [f"missing required event type {t!r}" for t in missing]


def test_valid_fixture_passes_schema_contract() -> None:
    data = _load_fixture()
    schema = _load_schema()
    errors = validate_schema_constraints(data, schema)
    errors.extend(_validate_required_event_types(data.get("events", [])))
    assert errors == [], "Schema violations:\n" + "\n".join(errors)


def test_schema_version_is_ailuros_timeline_v0() -> None:
    schema = _load_schema()
    sv = schema.get("properties", {}).get("schema_version", {})
    assert sv.get("const") == "ailuros.timeline.v0"


def test_events_has_required_fields_in_schema() -> None:
    schema = _load_schema()
    items = schema.get("properties", {}).get("events", {}).get("items", {})
    required = items.get("required", [])
    assert "event" in required
    assert "run_id" in required
    assert "timestamp" in required


def test_minimal_invalid_sample_fails() -> None:
    bad = {
        "schema_version": "wrong.version",
        "run_id": "",
        "created_at": None,
        "events": [],
    }
    schema = _load_schema()
    errors = validate_schema_constraints(bad, schema)
    assert errors, "Expected schema errors for invalid sample"
    error_text = "\n".join(errors)
    assert "wrong.version" in error_text
    assert "run_id" in error_text
    assert "created_at" in error_text
    assert "events" in error_text


def test_missing_events_array_fails() -> None:
    bad = {
        "schema_version": "ailuros.timeline.v0",
        "run_id": "test-run",
        "created_at": "2026-01-01T00:00:00Z",
        "events": [],
    }
    schema = _load_schema()
    errors = validate_schema_constraints(bad, schema)
    assert errors, "Expected schema errors for empty events"
