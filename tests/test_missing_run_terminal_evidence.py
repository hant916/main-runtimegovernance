from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ailuros.core.execution import (
    EvidenceRef,
    ExecutionProjection,
    Lifecycle,
    Outcome,
    Scope,
    Validation,
)
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


# ── Explicit run-start evidence, not an EvidenceRef proxy (pack 8100) ────


def _projection(
    *,
    lifecycle: Lifecycle,
    evidence_refs: list[EvidenceRef],
) -> ExecutionProjection:
    """A projection assembled directly, bypassing the event path.

    ``started_at`` is required and non-nullable on the model, so it cannot
    express "no start observed"; the lifecycle projection is the only field
    that carries that fact.
    """
    return ExecutionProjection(
        run_id="run-1",
        source="source-a",
        schema_version="1.0",
        lifecycle=lifecycle,
        outcome=Outcome.UNKNOWN,
        validation=Validation.UNKNOWN,
        scope=Scope.UNKNOWN,
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        evidence_refs=evidence_refs,
    )


def test_started_at_alone_cannot_prove_a_run_started() -> None:
    # started_at is always populated (the projection falls back to now()), so a
    # non-RUNNING projection with unrelated refs must stay silent.
    projection = _projection(
        lifecycle=Lifecycle.UNKNOWN,
        evidence_refs=[EvidenceRef(event_id="role-1"), EvidenceRef(event_id="dec-1")],
    )
    types = [signal.type for signal in derive_signals(projection)]

    assert SignalType.MISSING_RUN_TERMINAL_EVIDENCE.value not in types


def test_unrelated_evidence_refs_alone_do_not_prove_a_run_started() -> None:
    # runtime_role / governance_decision evidence populates evidence_refs
    # without any run_started event; lifecycle stays UNKNOWN and nothing fires.
    events = [
        _event("runtime_role", "role-1"),
        _event("governance_decision", "dec-1"),
    ]
    projection = build_execution_projection("run-1", "source-a", events)

    assert projection.lifecycle != Lifecycle.RUNNING
    assert SignalType.MISSING_RUN_TERMINAL_EVIDENCE.value not in _signal_types(events)


def test_observed_run_start_signals_even_without_evidence_refs() -> None:
    # The false-negative case: start observed, but no usable provenance ref.
    projection = _projection(lifecycle=Lifecycle.RUNNING, evidence_refs=[])
    types = [signal.type for signal in derive_signals(projection)]

    assert SignalType.MISSING_RUN_TERMINAL_EVIDENCE.value in types


def test_empty_run_start_event_id_still_counts_as_start_evidence() -> None:
    # Provenance quality is degraded, but the run_started fact was observed:
    # an empty event_id must not erase it.
    events = [_event("run_started", "")]
    projection = build_execution_projection("run-1", "source-a", events)

    assert projection.lifecycle == Lifecycle.RUNNING
    types = [signal.type for signal in derive_signals(projection)]
    assert SignalType.MISSING_RUN_TERMINAL_EVIDENCE.value in types


def test_terminal_lifecycles_stay_silent_regardless_of_refs() -> None:
    for lifecycle in (Lifecycle.COMPLETED, Lifecycle.FAILED):
        projection = _projection(
            lifecycle=lifecycle,
            evidence_refs=[EvidenceRef(event_id="started")],
        )
        types = [signal.type for signal in derive_signals(projection)]
        assert SignalType.MISSING_RUN_TERMINAL_EVIDENCE.value not in types
