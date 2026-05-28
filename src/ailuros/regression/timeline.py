from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from ailuros.models import RuntimeEvent, RuntimeEventType

VALID_DECISION_ALLOWED_MAP: dict[str, bool | None] = {
    "allow": True,
    "warn": True,
    "sanitize": True,
    "require_review": False,
    "block": False,
}


class RegressionTimelineResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeline_path: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    failures: list[str] = []

    @property
    def passed(self) -> bool:
        return self.failed_cases == 0 and not self.failures


def _validate_decision(event: RuntimeEvent) -> str | None:
    payload = event.payload
    decision: Any = payload.get("decision", "")
    allowed: Any = payload.get("allowed")

    expected_allowed = VALID_DECISION_ALLOWED_MAP.get(decision)
    if expected_allowed is None:
        return (
            f"event {event.event_id}: unknown decision type {decision!r}"
        )

    if allowed is not expected_allowed:
        return (
            f"event {event.event_id}: decision={decision!r} expected "
            f"allowed={expected_allowed} got allowed={allowed}"
        )

    return None


def _load_timeline_events(path: Path) -> list[RuntimeEvent] | RegressionTimelineResult:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return RegressionTimelineResult(
            timeline_path=str(path),
            total_cases=0,
            passed_cases=0,
            failed_cases=0,
            failures=[f"invalid timeline file: {exc}"],
        )

    if not isinstance(raw, list):
        return RegressionTimelineResult(
            timeline_path=str(path),
            total_cases=0,
            passed_cases=0,
            failed_cases=0,
            failures=["timeline must be a JSON array of RuntimeEvent objects"],
        )

    try:
        return [RuntimeEvent.model_validate(item) for item in raw]
    except (ValueError, TypeError) as exc:
        return RegressionTimelineResult(
            timeline_path=str(path),
            total_cases=0,
            passed_cases=0,
            failed_cases=0,
            failures=[f"invalid event data: {exc}"],
        )


def replay_timeline(timeline_path: str | Path) -> RegressionTimelineResult:
    path = Path(timeline_path)

    if not path.exists():
        return RegressionTimelineResult(
            timeline_path=str(path),
            total_cases=0,
            passed_cases=0,
            failed_cases=0,
            failures=[f"timeline not found: {path}"],
        )

    events_or_error = _load_timeline_events(path)
    if isinstance(events_or_error, RegressionTimelineResult):
        return events_or_error

    decision_events = [
        e for e in events_or_error
        if e.event_type == RuntimeEventType.GOVERNANCE_DECISION
    ]

    failures: list[str] = []
    for event in decision_events:
        reason = _validate_decision(event)
        if reason:
            failures.append(reason)

    total = len(decision_events)
    failed = len(failures)
    passed = total - failed

    return RegressionTimelineResult(
        timeline_path=str(path),
        total_cases=total,
        passed_cases=passed,
        failed_cases=failed,
        failures=failures,
    )
