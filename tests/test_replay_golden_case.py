import json
from pathlib import Path

from ailuros.regression.timeline import replay_timeline

HERE = Path(__file__).parent
FIXTURE = HERE / "golden" / "replay_minimal_timeline.json"

EXPECTED_EVENT_TYPES = [
    "run_started",
    "tool_call_requested",
    "governance_decision",
    "tool_call_executed",
    "tool_result_received",
    "run_completed",
]


def test_replay_minimal_timeline() -> None:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(raw) == len(EXPECTED_EVENT_TYPES)

    event_types = [e["event_type"] for e in raw]
    assert event_types == EXPECTED_EVENT_TYPES, (
        f"Event type sequence mismatch:\n"
        f"  expected: {EXPECTED_EVENT_TYPES}\n"
        f"  actual:   {event_types}"
    )

    sequences = [e["sequence"] for e in raw]
    assert sequences == list(range(1, len(raw) + 1)), (
        f"Sequence must be 1..{len(raw)} in order, got {sequences}"
    )

    for i, e in enumerate(raw):
        assert "timestamp" in e, f"Event {i} missing timestamp"
        assert e["timestamp"].endswith("+00:00"), (
            f"Event {i} timestamp must be normalized UTC, got {e['timestamp']}"
        )

    result = replay_timeline(FIXTURE)
    assert result.passed, (
        f"Replay golden case failed:\n"
        f"  total:   {result.total_cases}\n"
        f"  passed:  {result.passed_cases}\n"
        f"  failed:  {result.failed_cases}\n"
        f"  failures: {result.failures}"
    )
    assert result.total_cases == 1
    assert result.passed_cases == 1
    assert result.failed_cases == 0
