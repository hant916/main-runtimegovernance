from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ailuros.core.execution import (
    BudgetRecord,
    EvidenceRef,
    ExecutionProjection,
    Lifecycle,
    Outcome,
    Scope,
    Validation,
)
from ailuros.projection import build_execution_projection
from ailuros.signals import SignalType, derive_signals


def _event(
    event_type: str,
    *,
    event_id: str | None = None,
    timestamp: datetime | None = None,
    payload: dict | None = None,
    step_id: str | None = None,
) -> dict:
    ts = timestamp or datetime.now(UTC)
    eid = event_id or f"evt-{event_type}"
    return {
        "event_id": eid,
        "event_type": event_type,
        "timestamp": ts,
        "payload": payload or {},
        "step_id": step_id,
    }


def _budget_event(
    event_id: str,
    *,
    subject: str = "subject",
    unit: str = "tokens",
    scope_ref: str | None = None,
    limit: float | int | None = None,
    consumed: float | int | None = None,
    remaining: float | int | None = None,
    status: str | None = None,
    required: bool | None = None,
) -> dict:
    payload: dict = {"subject": subject, "unit": unit}
    if scope_ref is not None:
        payload["scope_ref"] = scope_ref
    if limit is not None:
        payload["limit"] = limit
    if consumed is not None:
        payload["consumed"] = consumed
    if remaining is not None:
        payload["remaining"] = remaining
    if status is not None:
        payload["status"] = status
    if required is not None:
        payload["required"] = required
    return _event("budget_evidence", event_id=event_id, payload=payload)


def _projection(
    *,
    run_id: str = "run-test",
    budget_records: list[BudgetRecord] | None = None,
) -> ExecutionProjection:
    now = datetime.now(UTC)
    return ExecutionProjection(
        run_id=run_id,
        source="test",
        schema_version="1.0",
        lifecycle=Lifecycle.COMPLETED,
        outcome=Outcome.SUCCESS,
        validation=Validation.PASSED,
        scope=Scope.CLEAN,
        started_at=now,
        completed_at=now,
        budget_records=budget_records or [],
    )


def _record(
    *,
    subject: str = "subject",
    unit: str = "tokens",
    scope_ref: str | None = None,
    limit: float | None = None,
    consumed: float | None = None,
    remaining: float | None = None,
    status: str = "unknown",
    required: bool | None = None,
    evidence_refs: list[EvidenceRef] | None = None,
) -> BudgetRecord:
    return BudgetRecord(
        subject=subject,
        unit=unit,
        scope_ref=scope_ref,
        limit=limit,
        consumed=consumed,
        remaining=remaining,
        status=status,
        required=required,
        evidence_refs=evidence_refs or [],
    )


# ── T1: BudgetRecord model ───────────────────────────────────────────────


def test_budget_record_creation() -> None:
    ref = EvidenceRef(event_id="evt-1")
    record = BudgetRecord(
        subject="run-budget",
        unit="tokens",
        scope_ref="scope-a",
        limit=1000.0,
        consumed=750.0,
        remaining=250.0,
        status="within",
        required=True,
        evidence_refs=[ref],
        source={"event_id": "evt-1"},
    )
    assert record.subject == "run-budget"
    assert record.unit == "tokens"
    assert record.scope_ref == "scope-a"
    assert record.limit == 1000.0
    assert record.consumed == 750.0
    assert record.remaining == 250.0
    assert record.status == "within"
    assert record.required is True
    assert record.evidence_refs == [ref]
    assert record.source == {"event_id": "evt-1"}


def test_budget_record_defaults() -> None:
    record = BudgetRecord(subject="run-budget", unit="requests")
    assert record.scope_ref is None
    assert record.limit is None
    assert record.consumed is None
    assert record.remaining is None
    assert record.status == "unknown"
    assert record.required is None
    assert record.evidence_refs == []
    assert record.source == {}


def test_budget_record_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        BudgetRecord(subject="run-budget", unit="tokens", price=3.0)


def test_budget_record_serializes_to_json() -> None:
    record = BudgetRecord(
        subject="run-budget",
        unit="EUR",
        limit=50.0,
        consumed=25.0,
        evidence_refs=[EvidenceRef(event_id="evt-1")],
    )
    data = record.model_dump(mode="json")
    assert data["subject"] == "run-budget"
    assert data["unit"] == "EUR"
    assert data["limit"] == 50.0
    assert data["consumed"] == 25.0
    assert data["remaining"] is None
    assert data["status"] == "unknown"
    assert data["evidence_refs"] == [
        {"event_id": "evt-1", "artifact": None, "pointer": None}
    ]


# ── T2: Project explicit budget evidence ─────────────────────────────────


def test_no_budget_events_yields_empty_records() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _event("run_completed", event_id="e2"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.budget_records == []


def test_successful_execution_is_not_proof_of_budget() -> None:
    events = [
        _event("run_started", event_id="e1"),
        _event("run_completed", event_id="e2"),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.outcome == Outcome.SUCCESS
    assert proj.budget_records == []


def test_budget_evidence_event_projected() -> None:
    events = [
        _budget_event(
            "e1",
            subject="run-budget",
            unit="requests",
            limit=100,
            consumed=40,
            status="within",
        ),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert len(proj.budget_records) == 1
    record = proj.budget_records[0]
    assert record.subject == "run-budget"
    assert record.unit == "requests"
    assert record.limit == 100.0
    assert record.consumed == 40.0
    assert record.status == "within"


def test_budget_event_without_subject_is_absent() -> None:
    events = [
        _event(
            "budget_evidence",
            event_id="e1",
            payload={"unit": "tokens", "limit": 10},
        ),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.budget_records == []


def test_budget_event_without_unit_is_absent() -> None:
    events = [
        _event(
            "budget_evidence",
            event_id="e1",
            payload={"subject": "run-budget", "limit": 10},
        ),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.budget_records == []


def test_budget_event_appears_in_evidence_refs() -> None:
    events = [
        _budget_event("e1", subject="run-budget", unit="tokens", limit=10),
    ]
    proj = build_execution_projection("run-1", "test", events)
    ref_ids = {r.event_id for r in proj.evidence_refs}
    assert "e1" in ref_ids
    record_ref_ids = {r.event_id for r in proj.budget_records[0].evidence_refs}
    assert "e1" in record_ref_ids


def test_budget_limit_is_not_estimated_when_absent() -> None:
    events = [
        _budget_event("e1", subject="run-budget", unit="tokens", consumed=40),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.budget_records[0].limit is None
    assert proj.budget_records[0].consumed == 40.0


# ── T3: Emit bounded budget signals ──────────────────────────────────────


def test_budget_exceeded_via_explicit_status() -> None:
    ref = EvidenceRef(event_id="evt-x")
    proj = _projection(
        budget_records=[
            _record(subject="run-budget", unit="tokens", status="exceeded",
                    evidence_refs=[ref]),
        ]
    )
    signals = derive_signals(proj)
    exceeded = [s for s in signals if s.type == SignalType.BUDGET_EXCEEDED.value]
    assert len(exceeded) == 1
    assert exceeded[0].severity == "high"
    assert exceeded[0].details["status"] == "exceeded"
    assert exceeded[0].evidence_refs == [ref]


def test_budget_exceeded_via_deterministic_consumed_over_limit() -> None:
    proj = _projection(
        budget_records=[
            _record(subject="run-budget", unit="requests", limit=100.0,
                    consumed=150.0),
        ]
    )
    signals = derive_signals(proj)
    exceeded = [s for s in signals if s.type == SignalType.BUDGET_EXCEEDED.value]
    assert len(exceeded) == 1
    assert exceeded[0].details["limit"] == 100.0
    assert exceeded[0].details["consumed"] == 150.0


def test_no_exceeded_when_consumed_at_or_below_limit() -> None:
    proj = _projection(
        budget_records=[
            _record(subject="run-budget", unit="tokens", limit=100.0,
                    consumed=100.0),
        ]
    )
    signals = derive_signals(proj)
    assert not any(s.type == SignalType.BUDGET_EXCEEDED.value for s in signals)


def test_no_exceeded_when_values_insufficient() -> None:
    proj = _projection(
        budget_records=[
            _record(subject="run-budget", unit="tokens", limit=None,
                    consumed=None),
        ]
    )
    signals = derive_signals(proj)
    assert not any(s.type == SignalType.BUDGET_EXCEEDED.value for s in signals)


def test_no_exceeded_when_no_evidence() -> None:
    proj = _projection()
    signals = derive_signals(proj)
    assert not any(s.type == SignalType.BUDGET_EXCEEDED.value for s in signals)


def test_budget_unknown_when_required_and_insufficient() -> None:
    ref = EvidenceRef(event_id="evt-u")
    proj = _projection(
        budget_records=[
            _record(subject="run-budget", unit="tokens", required=True,
                    evidence_refs=[ref]),
        ]
    )
    signals = derive_signals(proj)
    unknown = [s for s in signals if s.type == SignalType.BUDGET_UNKNOWN.value]
    assert len(unknown) == 1
    assert unknown[0].severity == "medium"
    assert unknown[0].evidence_refs == [ref]


def test_no_unknown_when_not_required() -> None:
    proj = _projection(
        budget_records=[
            _record(subject="run-budget", unit="tokens"),
        ]
    )
    signals = derive_signals(proj)
    assert not any(s.type == SignalType.BUDGET_UNKNOWN.value for s in signals)


def test_no_unknown_when_values_sufficient() -> None:
    proj = _projection(
        budget_records=[
            _record(subject="run-budget", unit="tokens", required=True,
                    limit=100.0, consumed=40.0),
        ]
    )
    signals = derive_signals(proj)
    assert not any(s.type == SignalType.BUDGET_UNKNOWN.value for s in signals)


def test_no_unknown_when_status_explicit() -> None:
    proj = _projection(
        budget_records=[
            _record(subject="run-budget", unit="tokens", required=True,
                    status="within"),
        ]
    )
    signals = derive_signals(proj)
    assert not any(s.type == SignalType.BUDGET_UNKNOWN.value for s in signals)


def test_signal_types_registered() -> None:
    assert SignalType.BUDGET_EXCEEDED.value == "budget_exceeded"
    assert SignalType.BUDGET_UNKNOWN.value == "budget_unknown"


# ── T4: Monetary and non-monetary units; no billing concept ──────────────


@pytest.mark.parametrize("unit", ["tokens", "requests", "EUR", "widgets"])
def test_budget_projection_accepts_explicit_units(unit: str) -> None:
    events = [
        _budget_event(
            "e1", subject="run-budget", unit=unit, limit=100, consumed=120,
        ),
    ]
    proj = build_execution_projection("run-1", "test", events)
    assert proj.budget_records[0].unit == unit
    signals = derive_signals(proj)
    assert any(s.type == SignalType.BUDGET_EXCEEDED.value for s in signals)


@pytest.mark.parametrize("unit", ["tokens", "requests", "EUR", "widgets"])
def test_budget_unknown_works_for_explicit_units(unit: str) -> None:
    proj = _projection(
        budget_records=[
            _record(subject="run-budget", unit=unit, required=True),
        ]
    )
    signals = derive_signals(proj)
    assert any(s.type == SignalType.BUDGET_UNKNOWN.value for s in signals)


def test_monetary_unit_is_not_special_cased() -> None:
    events = [
        _budget_event(
            "e1", subject="run-budget", unit="EUR", limit=50, consumed=60,
        ),
    ]
    proj = build_execution_projection("run-1", "test", events)
    record = proj.budget_records[0]
    assert record.unit == "EUR"
    assert record.limit == 50.0
    assert record.consumed == 60.0


def test_no_billing_or_payment_concept_in_source() -> None:
    import inspect

    import ailuros.core.execution as execution_module
    import ailuros.projection as projection_module
    import ailuros.signals as signals_module

    forbidden = (
        "invoice",
        "subscription",
        "pricing",
        "payment",
        "wallet",
        "stripe",
        "transport_charge",
        "price",
        "billing",
    )
    for module in (execution_module, projection_module, signals_module):
        source = inspect.getsource(module).lower()
        for token in forbidden:
            assert token not in source, (
                f"{module.__name__} contains forbidden billing token {token!r}"
            )
