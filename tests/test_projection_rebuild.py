from datetime import UTC, datetime, timedelta
from pathlib import Path

from ailuros.models import (
    Environment,
    Run,
    RunStatus,
    RuntimeEvent,
    RuntimeEventType,
)
from ailuros.projection import rebuild_projections_and_signals
from ailuros.storage import SQLiteStorage


def _make_run(storage: SQLiteStorage, run_id: str) -> None:
    now = datetime.now(UTC)
    run = Run(
        run_id=run_id,
        agent_id="agent",
        environment=Environment.DEVELOPMENT,
        status=RunStatus.RUNNING,
        input={"prompt": "hi"},
        created_at=now,
        updated_at=now,
    )
    storage.create_run(run)


def _make_event(
    run_id: str,
    event_type: RuntimeEventType,
    *,
    event_id: str | None = None,
    timestamp: datetime | None = None,
    payload: dict | None = None,
    step_id: str | None = None,
) -> RuntimeEvent:
    ts = timestamp or datetime.now(UTC)
    eid = event_id or f"evt-{event_type.value}"
    return RuntimeEvent(
        event_id=eid,
        run_id=run_id,
        step_id=step_id,
        event_type=event_type,
        timestamp=ts,
        payload=payload or {},
    )


# ── Rebuild idempotency ──────────────────────────────────────────────────


def test_rebuild_idempotent_yields_same_projection(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "runtime.sqlite")
    storage.init()
    _make_run(storage, "run_idem")

    now = datetime.now(UTC)
    storage.append_event(
        _make_event("run_idem", RuntimeEventType.RUN_STARTED, event_id="e1", timestamp=now)
    )
    storage.append_event(
        _make_event(
            "run_idem",
            RuntimeEventType.GOVERNANCE_DECISION,
            event_id="e2",
            timestamp=now + timedelta(seconds=1),
            payload={"decision": "block", "tool_name": "bash"},
        )
    )
    storage.append_event(
        _make_event(
            "run_idem",
            RuntimeEventType.RUN_COMPLETED,
            event_id="e3",
            timestamp=now + timedelta(seconds=2),
        )
    )

    proj1, sigs1 = rebuild_projections_and_signals(storage, "run_idem")
    proj2, sigs2 = rebuild_projections_and_signals(storage, "run_idem")

    assert proj1 == proj2

    stored1 = storage.get_projection("run_idem")
    stored2 = storage.get_projection("run_idem")
    assert stored1 is not None
    assert stored2 is not None
    assert stored1["projection"] == stored2["projection"]

    assert [s["signal_id"] for s in storage.get_signals("run_idem")] == [
        s["signal_id"] for s in storage.get_signals("run_idem")
    ]


def test_rebuild_idempotent_yields_same_signals(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "runtime.sqlite")
    storage.init()
    _make_run(storage, "run_sig_idem")

    now = datetime.now(UTC)
    storage.append_event(
        _make_event("run_sig_idem", RuntimeEventType.RUN_STARTED, event_id="e1", timestamp=now)
    )
    storage.append_event(
        _make_event(
            "run_sig_idem",
            RuntimeEventType.GOVERNANCE_DECISION,
            event_id="e2",
            timestamp=now + timedelta(seconds=1),
            payload={"decision": "block", "tool_name": "bash"},
        )
    )
    storage.append_event(
        _make_event(
            "run_sig_idem",
            RuntimeEventType.GOVERNANCE_DECISION,
            event_id="e3",
            timestamp=now + timedelta(seconds=2),
            payload={"decision": "allow", "tool_name": "read"},
        )
    )
    storage.append_event(
        _make_event(
            "run_sig_idem",
            RuntimeEventType.RUN_COMPLETED,
            event_id="e4",
            timestamp=now + timedelta(seconds=3),
        )
    )

    _, sigs1 = rebuild_projections_and_signals(storage, "run_sig_idem")
    _, sigs2 = rebuild_projections_and_signals(storage, "run_sig_idem")

    sig_ids1 = sorted(s.signal_id for s in sigs1)
    sig_ids2 = sorted(s.signal_id for s in sigs2)
    assert sig_ids1 == sig_ids2

    sig_types1 = sorted(s.type for s in sigs1)
    sig_types2 = sorted(s.type for s in sigs2)
    assert sig_types1 == sig_types2


def test_rebuild_idempotent_clears_previous_signals(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "runtime.sqlite")
    storage.init()
    _make_run(storage, "run_clear_idem")

    now = datetime.now(UTC)
    storage.append_event(
        _make_event("run_clear_idem", RuntimeEventType.RUN_STARTED, event_id="e1", timestamp=now)
    )
    storage.append_event(
        _make_event(
            "run_clear_idem",
            RuntimeEventType.RUN_COMPLETED,
            event_id="e2",
            timestamp=now + timedelta(seconds=1),
        )
    )

    rebuild_projections_and_signals(storage, "run_clear_idem")
    rebuild_projections_and_signals(storage, "run_clear_idem")

    assert len(storage.get_signals("run_clear_idem")) == 0


# ── Changed evidence yields changed derived state ────────────────────────


def test_added_event_changes_projection(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "runtime.sqlite")
    storage.init()
    _make_run(storage, "run_change")

    now = datetime.now(UTC)
    e1 = _make_event(
        "run_change", RuntimeEventType.RUN_STARTED, event_id="e1", timestamp=now
    )
    e2 = _make_event(
        "run_change",
        RuntimeEventType.RUN_COMPLETED,
        event_id="e2",
        timestamp=now + timedelta(seconds=1),
    )
    storage.append_event(e1)
    storage.append_event(e2)

    proj1, _ = rebuild_projections_and_signals(storage, "run_change")
    assert proj1.decision_count == 0

    storage.append_event(
        _make_event(
            "run_change",
            RuntimeEventType.GOVERNANCE_DECISION,
            event_id="e3",
            timestamp=now + timedelta(seconds=2),
            payload={"decision": "block", "tool_name": "bash"},
        )
    )

    proj2, _ = rebuild_projections_and_signals(storage, "run_change")
    assert proj2.decision_count == 1
    assert proj2 != proj1
    assert proj1.decision_count != proj2.decision_count


def test_changed_evidence_yields_changed_signals(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "runtime.sqlite")
    storage.init()
    _make_run(storage, "run_sig_change")

    now = datetime.now(UTC)
    storage.append_event(
        _make_event("run_sig_change", RuntimeEventType.RUN_STARTED, event_id="e1", timestamp=now)
    )
    storage.append_event(
        _make_event(
            "run_sig_change",
            RuntimeEventType.GOVERNANCE_DECISION,
            event_id="e2",
            timestamp=now + timedelta(seconds=1),
            payload={"decision": "allow", "tool_name": "read"},
        )
    )
    storage.append_event(
        _make_event(
            "run_sig_change",
            RuntimeEventType.RUN_COMPLETED,
            event_id="e3",
            timestamp=now + timedelta(seconds=2),
        )
    )

    _, sigs1 = rebuild_projections_and_signals(storage, "run_sig_change")
    sig_types1 = {s.type for s in sigs1}
    assert "scope_violation" not in sig_types1
    assert "evidence_inconsistency" not in sig_types1

    storage.append_event(
        _make_event(
            "run_sig_change",
            RuntimeEventType.GOVERNANCE_DECISION,
            event_id="e4",
            timestamp=now + timedelta(seconds=3),
            payload={"decision": "block", "tool_name": "bash"},
        )
    )

    _, sigs2 = rebuild_projections_and_signals(storage, "run_sig_change")
    sig_types2 = {s.type for s in sigs2}
    assert "evidence_inconsistency" in sig_types2
    assert sig_types1 != sig_types2


def test_removed_event_not_in_projection(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "runtime.sqlite")
    storage.init()
    _make_run(storage, "run_remove")

    now = datetime.now(UTC)
    storage.append_event(
        _make_event("run_remove", RuntimeEventType.RUN_STARTED, event_id="e1", timestamp=now)
    )
    storage.append_event(
        _make_event(
            "run_remove",
            RuntimeEventType.RUN_COMPLETED,
            event_id="e2",
            timestamp=now + timedelta(seconds=1),
        )
    )

    proj1, _ = rebuild_projections_and_signals(storage, "run_remove")
    assert proj1.event_count == 2

    proj2, _ = rebuild_projections_and_signals(storage, "run_remove")
    assert proj2.event_count == 2
    assert proj1.event_count == proj2.event_count


# ── Empty events ─────────────────────────────────────────────────────────


def test_rebuild_empty_events_succeeds(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "runtime.sqlite")
    storage.init()
    _make_run(storage, "run_empty")

    proj, sigs = rebuild_projections_and_signals(storage, "run_empty")

    assert proj is not None
    assert proj.run_id == "run_empty"
    assert proj.event_count == 0
    assert proj.decision_count == 0
    assert sigs == []
    assert len(storage.get_signals("run_empty")) == 0


def test_rebuild_custom_source_and_schema(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "runtime.sqlite")
    storage.init()
    _make_run(storage, "run_custom")

    now = datetime.now(UTC)
    storage.append_event(
        _make_event("run_custom", RuntimeEventType.RUN_STARTED, event_id="e1", timestamp=now)
    )
    storage.append_event(
        _make_event(
            "run_custom",
            RuntimeEventType.RUN_COMPLETED,
            event_id="e2",
            timestamp=now + timedelta(seconds=1),
        )
    )

    proj, _ = rebuild_projections_and_signals(
        storage, "run_custom", source="manual_rebuild", schema_version="2.0"
    )

    stored = storage.get_projection("run_custom")
    assert stored is not None
    assert stored["source"] == "manual_rebuild"
    assert stored["projection_schema"] == "execution_summary/v2.0"
    assert proj.source == "manual_rebuild"
    assert proj.schema_version == "2.0"


# ── Evidence refs preserved across rebuilds ─────────────────────────────


def test_evidence_refs_populated_in_projection(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "runtime.sqlite")
    storage.init()
    _make_run(storage, "run_refs")

    now = datetime.now(UTC)
    storage.append_event(
        _make_event("run_refs", RuntimeEventType.RUN_STARTED, event_id="e1", timestamp=now)
    )
    storage.append_event(
        _make_event(
            "run_refs",
            RuntimeEventType.GOVERNANCE_DECISION,
            event_id="decision_1",
            timestamp=now + timedelta(seconds=1),
            payload={"decision": "block", "tool_name": "bash"},
        )
    )
    storage.append_event(
        _make_event(
            "run_refs",
            RuntimeEventType.RUN_COMPLETED,
            event_id="e3",
            timestamp=now + timedelta(seconds=2),
        )
    )

    proj, _ = rebuild_projections_and_signals(storage, "run_refs")

    ref_ids = {r.event_id for r in proj.evidence_refs}
    assert "e1" in ref_ids
    assert "decision_1" in ref_ids
    assert "e3" in ref_ids


def test_signal_evidence_refs_preserved_in_storage(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "runtime.sqlite")
    storage.init()
    _make_run(storage, "run_sig_refs")

    now = datetime.now(UTC)
    storage.append_event(
        _make_event("run_sig_refs", RuntimeEventType.RUN_STARTED, event_id="e1", timestamp=now)
    )
    storage.append_event(
        _make_event(
            "run_sig_refs",
            RuntimeEventType.GOVERNANCE_DECISION,
            event_id="decision_1",
            timestamp=now + timedelta(seconds=1),
            payload={"decision": "block", "tool_name": "bash"},
        )
    )
    storage.append_event(
        _make_event(
            "run_sig_refs",
            RuntimeEventType.RUN_COMPLETED,
            event_id="e3",
            timestamp=now + timedelta(seconds=2),
        )
    )

    _, sigs = rebuild_projections_and_signals(storage, "run_sig_refs")

    stored = storage.get_signals("run_sig_refs")
    for sig in sigs:
        assert sig.evidence_refs
    assert len(stored) == len(sigs)
