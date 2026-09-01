from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ailuros.core.execution import Lifecycle
from ailuros.projection import build_execution_projection
from ailuros.signals import SignalType, derive_signals


def _event(event_type: str, event_id: str) -> dict:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "timestamp": datetime(2026, 1, 1, tzinfo=UTC),
        "payload": {},
    }


def _signal_types(events: list[dict], *, source: str = "source-a") -> list[str]:
    projection = build_execution_projection("run-1", source, events)
    return [signal.type for signal in derive_signals(projection)]


def test_completed_run_does_not_emit_missing_terminal_evidence() -> None:
    events = [
        _event("run_started", "started"),
        _event("run_completed", "completed"),
    ]

    projection = build_execution_projection("run-1", "source-a", events)

    assert projection.lifecycle == Lifecycle.COMPLETED
    assert SignalType.MISSING_RUN_TERMINAL_EVIDENCE.value not in _signal_types(events)


def test_failed_run_does_not_emit_missing_terminal_evidence() -> None:
    events = [_event("run_started", "started"), _event("run_failed", "failed")]

    projection = build_execution_projection("run-1", "source-a", events)

    assert projection.lifecycle == Lifecycle.FAILED
    assert SignalType.MISSING_RUN_TERMINAL_EVIDENCE.value not in _signal_types(events)


@pytest.mark.parametrize("source", ["source-a", "source-b"])
def test_started_run_without_terminal_emits_source_neutral_finding(source: str) -> None:
    events = [_event("run_started", "started")]

    projection = build_execution_projection("run-1", source, events)
    signals = derive_signals(projection)

    assert projection.lifecycle == Lifecycle.RUNNING
    assert [signal.type for signal in signals] == [
        SignalType.MISSING_RUN_TERMINAL_EVIDENCE.value
    ]
    assert signals[0].severity == "medium"
    assert signals[0].subject == "run"
    assert signals[0].details == {
        "lifecycle": "running",
        "terminal_evidence": "missing",
    }
    assert signals[0].evidence_refs[0].event_id == "started"


def test_no_start_does_not_emit_missing_terminal_evidence() -> None:
    assert _signal_types([]) == []
