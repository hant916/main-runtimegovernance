from datetime import UTC, datetime
from pathlib import Path

from ailuros.models import (
    Environment,
    Run,
    RunStatus,
    RuntimeEvent,
    RuntimeEventType,
)
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


def test_init_creates_new_tables(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "runtime.sqlite")
    storage.init()

    with storage._connect() as conn:  # noqa: SLF001
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "projections" in tables
    assert "signals" in tables


def test_init_is_idempotent_for_projection_tables(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "runtime.sqlite")
    storage.init()
    storage.init()
    _make_run(storage, "run_1")
    assert storage.get_run("run_1").run_id == "run_1"


def test_upsert_and_get_projection(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "runtime.sqlite")
    storage.init()
    _make_run(storage, "run_proj")

    storage.upsert_projection(
        run_id="run_proj",
        projection_schema="execution_summary/v1",
        projection_version="1.0",
        source="evaluation",
        projection_json={"status": "passed", "score": 0.95},
        lifecycle_status="completed",
        outcome_summary="All checks passed",
        validation_summary="5/5 validators green",
    )

    proj = storage.get_projection("run_proj")
    assert proj is not None
    assert proj["run_id"] == "run_proj"
    assert proj["projection_schema"] == "execution_summary/v1"
    assert proj["projection_version"] == "1.0"
    assert proj["source"] == "evaluation"
    assert proj["lifecycle_status"] == "completed"
    assert proj["outcome_summary"] == "All checks passed"
    assert proj["validation_summary"] == "5/5 validators green"
    assert proj["projection"] == {"status": "passed", "score": 0.95}
    assert isinstance(proj["updated_at"], datetime)


def test_upsert_projection_rebuild_overwrites(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "runtime.sqlite")
    storage.init()
    _make_run(storage, "run_rebuild")

    storage.upsert_projection(
        run_id="run_rebuild",
        projection_schema="schema/v1",
        projection_version="1",
        source="old",
        projection_json={"v": 1},
    )
    original = storage.get_projection("run_rebuild")
    assert original is not None

    storage.upsert_projection(
        run_id="run_rebuild",
        projection_schema="schema/v1",
        projection_version="2",
        source="new",
        projection_json={"v": 2},
        lifecycle_status="updated",
    )
    updated = storage.get_projection("run_rebuild")
    assert updated is not None
    assert updated["projection_version"] == "2"
    assert updated["source"] == "new"
    assert updated["projection"] == {"v": 2}
    assert updated["lifecycle_status"] == "updated"
    assert updated["updated_at"] >= original["updated_at"]


def test_get_projection_missing_returns_none(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "runtime.sqlite")
    storage.init()
    assert storage.get_projection("no_such_run") is None


def test_replace_and_get_signals(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "runtime.sqlite")
    storage.init()
    _make_run(storage, "run_sig")

    now = datetime.now(UTC).isoformat()
    signals = [
        {
            "signal_id": "sig_1",
            "type": "anomaly",
            "severity": "high",
            "subject": "unexpected_output",
            "evidence_refs": ["evt_1", "evt_2"],
            "details": {"reason": "value out of range"},
            "created_at": now,
        },
        {
            "signal_id": "sig_2",
            "type": "warning",
            "severity": "medium",
            "subject": "policy_near_boundary",
            "evidence_refs": ["evt_3"],
            "details": {},
            "created_at": now,
        },
    ]
    storage.replace_signals("run_sig", signals)

    stored = storage.get_signals("run_sig")
    assert len(stored) == 2
    assert stored[0]["signal_id"] == "sig_1"
    assert stored[0]["type"] == "anomaly"
    assert stored[0]["severity"] == "high"
    assert stored[0]["subject"] == "unexpected_output"
    assert stored[0]["evidence_refs"] == ["evt_1", "evt_2"]
    assert stored[0]["details"] == {"reason": "value out of range"}
    assert stored[1]["signal_id"] == "sig_2"


def test_replace_signals_clears_previous_for_run(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "runtime.sqlite")
    storage.init()
    _make_run(storage, "run_clear")

    storage.replace_signals(
        "run_clear",
        [{"signal_id": "sig_old", "type": "info", "severity": "low", "subject": "x"}],
    )
    assert len(storage.get_signals("run_clear")) == 1

    storage.replace_signals(
        "run_clear",
        [
            {"signal_id": "sig_new_1", "type": "info", "severity": "low", "subject": "a"},
            {"signal_id": "sig_new_2", "type": "info", "severity": "low", "subject": "b"},
        ],
    )
    assert len(storage.get_signals("run_clear")) == 2
    ids = [s["signal_id"] for s in storage.get_signals("run_clear")]
    assert "sig_old" not in ids
    assert "sig_new_1" in ids
    assert "sig_new_2" in ids


def test_rebuild_does_not_touch_events(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "runtime.sqlite")
    storage.init()
    _make_run(storage, "run_events")

    now = datetime.now(UTC)
    for i in range(3):
        storage.append_event(
            RuntimeEvent(
                event_id=f"evt_{i}",
                run_id="run_events",
                event_type=RuntimeEventType.RUN_STARTED,
                timestamp=now,
                payload={"i": i},
            )
        )

    events_before = storage.list_events("run_events")
    assert len(events_before) == 3

    storage.upsert_projection(
        run_id="run_events",
        projection_schema="s/v1",
        projection_version="1",
        source="rebuild",
        projection_json={"r": 1},
    )
    storage.replace_signals(
        "run_events",
        [{"signal_id": "sig_r", "type": "rebuild", "severity": "low", "subject": "test"}],
    )

    storage.upsert_projection(
        run_id="run_events",
        projection_schema="s/v1",
        projection_version="2",
        source="rebuild_again",
        projection_json={"r": 2},
    )
    storage.replace_signals(
        "run_events",
        [{"signal_id": "sig_r2", "type": "rebuild", "severity": "low", "subject": "test2"}],
    )

    events_after = storage.list_events("run_events")
    assert len(events_after) == 3
    assert [e.event_id for e in events_after] == [e.event_id for e in events_before]

    proj = storage.get_projection("run_events")
    assert proj is not None
    assert proj["projection"] == {"r": 2}

    sigs = storage.get_signals("run_events")
    assert len(sigs) == 1
    assert sigs[0]["signal_id"] == "sig_r2"
