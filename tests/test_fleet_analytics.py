from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from ailuros.analytics import build_fleet_overview
from ailuros.models import Environment, Run, RunStatus
from ailuros.storage import SQLiteStorage


def _make_run_with_projection(
    storage: SQLiteStorage,
    run_id: str,
    source: str,
    outcome: str | None,
    validation: str | None,
    scope: str | None,
    created_at: datetime,
) -> None:
    run = Run(
        run_id=run_id,
        agent_id="agent",
        environment=Environment.DEVELOPMENT,
        status=RunStatus.COMPLETED,
        input={"prompt": "hi"},
        created_at=created_at,
        updated_at=created_at,
    )
    storage.create_run(run)
    storage.upsert_projection(
        run_id=run_id,
        projection_schema="execution_summary/v1.0",
        projection_version="1.0.0",
        source=source,
        projection_json={
            "run_id": run_id,
            "scope": scope,
        },
        lifecycle_status="completed",
        outcome_summary=outcome,
        validation_summary=validation,
    )


def test_empty_window(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "fleet.sqlite")
    storage.init()

    now = datetime.now(UTC)
    overview = build_fleet_overview(storage, now - timedelta(hours=1), now)

    assert overview.total_runs == 0
    assert overview.outcomes == {}
    assert overview.validations == {}
    assert overview.scopes == {}
    assert overview.fallback_count == 0
    assert overview.fallback_rate == 0.0
    assert overview.signals == {}
    assert overview.sources == {}
    assert overview.source_filter is None


def test_mixed_outcomes_and_unknowns(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "fleet.sqlite")
    storage.init()
    now = datetime.now(UTC)

    _make_run_with_projection(
        storage, "r1", "sdk", "success", "passed", "clean",
        now - timedelta(minutes=10),
    )
    _make_run_with_projection(
        storage, "r2", "sdk", "partial", "failed", "violated",
        now - timedelta(minutes=5),
    )
    _make_run_with_projection(
        storage, "r3", "sdk", None, None, None,
        now - timedelta(minutes=2),
    )

    storage.replace_signals("r2", [
        {
            "signal_id": "sig_a",
            "type": "backend_fallback",
            "severity": "medium",
            "subject": "backend",
        },
        {
            "signal_id": "sig_b",
            "type": "validation_failure",
            "severity": "high",
            "subject": "validation",
        },
    ])

    window_start = now - timedelta(hours=1)
    window_end = now
    overview = build_fleet_overview(storage, window_start, window_end)

    assert overview.total_runs == 3
    assert overview.outcomes == {"success": 1, "partial": 1, "unknown": 1}
    assert overview.validations == {"passed": 1, "failed": 1, "unknown": 1}
    assert overview.scopes == {"clean": 1, "violated": 1, "unknown": 1}
    assert overview.fallback_count == 1
    assert overview.fallback_rate == 1.0 / 3.0
    assert overview.signals == {"backend_fallback": 1, "validation_failure": 1}
    assert overview.sources == {"sdk": 3}
    assert overview.source_filter is None


def test_multiple_sources(tmp_path: Path) -> None:
    storage = SQLiteStorage(tmp_path / "fleet.sqlite")
    storage.init()
    now = datetime.now(UTC)

    _make_run_with_projection(
        storage, "rA", "sdk", "success", "passed", "clean",
        now - timedelta(minutes=10),
    )
    _make_run_with_projection(
        storage, "rB", "cli", "success", "passed", "clean",
        now - timedelta(minutes=5),
    )
    _make_run_with_projection(
        storage, "rC", "sdk", "failed", "failed", "violated",
        now - timedelta(minutes=2),
    )

    window_start = now - timedelta(hours=1)

    overview_all = build_fleet_overview(storage, window_start, now)
    assert overview_all.total_runs == 3
    assert overview_all.sources == {"sdk": 2, "cli": 1}
    assert overview_all.outcomes == {"success": 2, "failed": 1}
    assert overview_all.source_filter is None

    overview_sdk = build_fleet_overview(storage, window_start, now, source="sdk")
    assert overview_sdk.total_runs == 2
    assert overview_sdk.sources == {"sdk": 2}
    assert overview_sdk.outcomes == {"success": 1, "failed": 1}
    assert overview_sdk.source_filter == "sdk"
