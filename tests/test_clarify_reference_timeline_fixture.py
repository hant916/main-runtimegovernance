from __future__ import annotations

import copy
import json
from pathlib import Path

from ailuros.adapters.clarify_timeline_contract import (
    REQUIRED_EVENT_TYPES,
    REQUIRED_SCHEMA_VERSION,
    validate_clarify_timeline,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "reference_apps"
    / "fixtures"
    / "clarify_timeline_v0.json"
)


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_real_clarify_fixture_matches_governance_mvp_contract() -> None:
    timeline = _load_fixture()

    assert timeline["schema_version"] == REQUIRED_SCHEMA_VERSION
    assert {event["event"] for event in timeline["events"]} >= REQUIRED_EVENT_TYPES
    assert validate_clarify_timeline(timeline) == []


def test_contract_rejects_legacy_fake_schema() -> None:
    timeline = copy.deepcopy(_load_fixture())
    timeline["schema_version"] = "1.0.0"

    errors = validate_clarify_timeline(timeline)

    assert any("invalid schema_version" in error for error in errors)


def test_contract_rejects_legacy_fake_event_set() -> None:
    timeline = copy.deepcopy(_load_fixture())
    timeline["events"] = [
        {
            "event": event_type,
            "run_id": timeline["run_id"],
            "timestamp": timeline["created_at"],
        }
        for event_type in (
            "clarify.timeline.start",
            "browser.navigation",
            "clarify.timeline.end",
        )
    ]

    errors = validate_clarify_timeline(timeline)

    for event_type in REQUIRED_EVENT_TYPES:
        assert any(event_type in error for error in errors)
