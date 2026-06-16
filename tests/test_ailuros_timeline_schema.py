from __future__ import annotations

import json
from pathlib import Path

SAMPLE_TIMELINE = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "clarify"
    / "evidence_bundle.sample"
    / "ailuros.timeline.v0.json"
)
SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "schemas"
    / "ailuros.timeline.v0.schema.json"
)

ALLOWED_EVENTS: frozenset[str] = frozenset({
    "INPUT_CLASSIFIED",
    "LLM_REQUEST",
    "LLM_RESPONSE",
    "EVALUATION_RESULT",
    "OUTPUT_GENERATED",
    "RUN_COMPLETED",
})


def _load_timeline() -> dict:
    return json.loads(SAMPLE_TIMELINE.read_text(encoding="utf-8"))


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validate_schema_contract(data: dict) -> list[str]:
    errors: list[str] = []

    if data.get("schema_version") != "ailuros.timeline.v0":
        errors.append(
            f"schema_version: expected 'ailuros.timeline.v0', got {data.get('schema_version')!r}"
        )

    run_id = data.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        errors.append("run_id: missing or empty")

    created_at = data.get("created_at")
    if not isinstance(created_at, str) or not created_at:
        errors.append("created_at: missing or empty")

    events = data.get("events")
    if not isinstance(events, list):
        errors.append("events: missing or not an array")
        return errors
    if not events:
        errors.append("events: empty array")

    for idx, event in enumerate(events):
        if not isinstance(event, dict):
            errors.append(f"events[{idx}]: not an object")
            continue

        ev = event.get("event")
        if not isinstance(ev, str) or not ev:
            errors.append(f"events[{idx}].event: missing or empty")
        elif ev not in ALLOWED_EVENTS:
            errors.append(f"events[{idx}].event: invalid name {ev!r}")

        ev_run_id = event.get("run_id")
        if not isinstance(ev_run_id, str) or not ev_run_id:
            errors.append(f"events[{idx}].run_id: missing or empty")

        timestamp = event.get("timestamp")
        if not isinstance(timestamp, str) or not timestamp:
            errors.append(f"events[{idx}].timestamp: missing or empty")

        extra = set(event.keys()) - {"event", "run_id", "timestamp", "metadata", "data"}
        if extra:
            errors.append(f"events[{idx}]: unexpected keys {sorted(extra)}")

    return errors


def test_schema_file_is_valid_json() -> None:
    schema = _load_schema()
    assert isinstance(schema, dict)
    assert schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"


def test_schema_defines_ailuros_timeline_v0() -> None:
    schema = _load_schema()
    sv = schema.get("properties", {}).get("schema_version", {})
    assert sv.get("const") == "ailuros.timeline.v0"


def test_schema_requires_enum_for_event_names() -> None:
    schema = _load_schema()
    items = schema.get("properties", {}).get("events", {}).get("items", {})
    event_prop = items.get("properties", {}).get("event", {})
    enum_vals = set(event_prop.get("enum", []))
    assert enum_vals == ALLOWED_EVENTS, f"Schema enum mismatch: {enum_vals ^ ALLOWED_EVENTS}"


def test_schema_requires_event_run_id_timestamp() -> None:
    schema = _load_schema()
    items = schema.get("properties", {}).get("events", {}).get("items", {})
    required = set(items.get("required", []))
    assert "event" in required
    assert "run_id" in required
    assert "timestamp" in required


def test_valid_sample_timeline_passes() -> None:
    data = _load_timeline()
    errors = _validate_schema_contract(data)
    assert errors == [], "Schema contract violations:\n" + "\n".join(errors)


def test_missing_schema_version_fails() -> None:
    data = _load_timeline()
    del data["schema_version"]
    errors = _validate_schema_contract(data)
    assert any("schema_version" in e for e in errors)


def test_wrong_schema_version_fails() -> None:
    data = _load_timeline()
    data["schema_version"] = "ailuros.timeline.v1"
    errors = _validate_schema_contract(data)
    assert any("v1" in e for e in errors)


def test_missing_events_fails() -> None:
    data = _load_timeline()
    del data["events"]
    errors = _validate_schema_contract(data)
    assert any("events" in e for e in errors)


def test_empty_events_fails() -> None:
    data = _load_timeline()
    data["events"] = []
    errors = _validate_schema_contract(data)
    assert any("empty" in e for e in errors)


def test_invalid_event_name_fails() -> None:
    data = _load_timeline()
    data["events"][0]["event"] = "INVALID_EVENT"
    errors = _validate_schema_contract(data)
    assert any("invalid name" in e for e in errors)


def test_quality_signals_missing_via_validator(tmp_path: Path) -> None:
    import shutil

    from scripts.validate_clarify_evidence_bundle import validate_bundle

    bundle_src = SAMPLE_TIMELINE.parents[0]
    bundle_dir = tmp_path / "bundle"
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    shutil.copytree(bundle_src, bundle_dir)

    timeline_path = bundle_dir / "ailuros.timeline.v0.json"
    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    for ev in timeline["events"]:
        if ev["event"] == "EVALUATION_RESULT" and "data" in ev:
            del ev["data"]["quality_signals"]
            break
    timeline_path.write_text(json.dumps(timeline), encoding="utf-8")

    checks, status = validate_bundle(bundle_dir)
    assert status == "FAIL"
    assert any("quality_signals is missing" in c.message for c in checks)


def test_non_boolean_quality_signal_fails_via_validator(tmp_path: Path) -> None:
    import shutil

    from scripts.validate_clarify_evidence_bundle import validate_bundle

    bundle_src = SAMPLE_TIMELINE.parents[0]
    bundle_dir = tmp_path / "bundle"
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    shutil.copytree(bundle_src, bundle_dir)

    timeline_path = bundle_dir / "ailuros.timeline.v0.json"
    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    for ev in timeline["events"]:
        if ev["event"] == "EVALUATION_RESULT" and "data" in ev:
            ev["data"]["quality_signals"]["json_valid"] = "yes"
            break
    timeline_path.write_text(json.dumps(timeline), encoding="utf-8")

    checks, status = validate_bundle(bundle_dir)
    assert status == "FAIL"
    assert any("Non-boolean" in c.message for c in checks)
