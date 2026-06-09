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


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _collect_errors(data: dict) -> list[str]:
    errors: list[str] = []

    if data.get("schema_version") != "ailuros.timeline.v0":
        errors.append("schema_version mismatch")

    run_id = data.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        errors.append("run_id missing or empty")

    created_at = data.get("created_at")
    if not isinstance(created_at, str) or not created_at:
        errors.append("created_at missing or empty")

    events = data.get("events")
    if not isinstance(events, list) or not events:
        errors.append("events missing or empty")
        return errors

    required_types: set[str] = {
        "INPUT_CLASSIFIED",
        "LLM_REQUEST",
        "LLM_RESPONSE",
        "EVALUATION_RESULT",
        "OUTPUT_GENERATED",
        "RUN_COMPLETED",
    }
    seen: set[str] = set()

    for idx, event in enumerate(events):
        if not isinstance(event, dict):
            errors.append(f"events[{idx}] not an object")
            continue
        et = event.get("event")
        if isinstance(et, str) and et:
            seen.add(et)
        else:
            errors.append(f"events[{idx}] missing event type")
        if not isinstance(event.get("run_id"), str):
            errors.append(f"events[{idx}] missing run_id")
        if not isinstance(event.get("timestamp"), str):
            errors.append(f"events[{idx}] missing timestamp")
        payload = event.get("metadata") or event.get("data")
        if payload is not None and not isinstance(payload, dict):
            errors.append(f"events[{idx}] payload must be an object if present")

    missing = sorted(required_types - seen)
    for t in missing:
        errors.append(f"missing required event type {t!r}")

    return errors


def test_valid_fixture_passes_contract() -> None:
    data = _load_fixture()
    errors = _collect_errors(data)
    assert errors == [], "Contract violations:\n" + "\n".join(errors)


def test_fixture_has_required_fields() -> None:
    data = _load_fixture()
    assert "schema_version" in data
    assert "run_id" in data
    assert "created_at" in data
    assert "events" in data
    assert len(data["events"]) == 6


def test_fixture_has_all_required_event_types() -> None:
    data = _load_fixture()
    event_types = {e["event"] for e in data["events"] if isinstance(e, dict)}
    required = {
        "INPUT_CLASSIFIED",
        "LLM_REQUEST",
        "LLM_RESPONSE",
        "EVALUATION_RESULT",
        "OUTPUT_GENERATED",
        "RUN_COMPLETED",
    }
    assert event_types >= required, f"Missing types: {required - event_types}"
