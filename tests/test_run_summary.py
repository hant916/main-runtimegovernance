from __future__ import annotations

from datetime import UTC, datetime

from ailuros.audit import RunSummary, build_run_summary
from ailuros.errors import AilurosNotFoundError
from ailuros.models import (
    Environment,
    Run,
    RunStatus,
    RuntimeEvent,
    RuntimeEventType,
)
from ailuros.storage import SQLiteStorage


def test_run_summary_contract_fields(tmp_path):
    storage = SQLiteStorage(tmp_path / "test.sqlite")
    storage.init()
    now = datetime.now(UTC)
    run = Run(
        run_id="sum-run-1",
        agent_id="agent",
        environment=Environment.DEVELOPMENT,
        status=RunStatus.COMPLETED,
        input="hello",
        created_at=now,
        updated_at=now,
    )
    storage.create_run(run)
    storage.append_event(RuntimeEvent(
        event_id="evt-1", run_id="sum-run-1",
        event_type=RuntimeEventType.RUN_STARTED,
        timestamp=now,
    ))
    storage.append_event(RuntimeEvent(
        event_id="evt-2", run_id="sum-run-1",
        event_type=RuntimeEventType.USER_INPUT_RECEIVED,
        timestamp=now, payload={"input": "hello"},
    ))
    storage.append_event(RuntimeEvent(
        event_id="evt-3", run_id="sum-run-1",
        event_type=RuntimeEventType.GOVERNANCE_DECISION,
        timestamp=now, payload={"decision": "allow"},
    ))
    storage.append_event(RuntimeEvent(
        event_id="evt-4", run_id="sum-run-1",
        event_type=RuntimeEventType.GOVERNANCE_DECISION,
        timestamp=now, payload={"decision": "block"},
    ))
    storage.append_event(RuntimeEvent(
        event_id="evt-5", run_id="sum-run-1",
        event_type=RuntimeEventType.RUN_COMPLETED,
        timestamp=now, payload={"status": "completed"},
    ))

    summary = build_run_summary(storage, "sum-run-1")

    assert isinstance(summary, RunSummary)
    assert summary.run_id == "sum-run-1"
    assert summary.status == "completed"
    assert summary.event_count == 5
    assert summary.decision_counts == {"allow": 1, "block": 1}
    assert summary.blocked_count == 1
    assert summary.review_count == 0
    assert summary.metadata_version == "1"
    assert summary.started_at is not None
    assert summary.completed_at is not None


def test_run_summary_no_decisions(tmp_path):
    storage = SQLiteStorage(tmp_path / "test.sqlite")
    storage.init()
    now = datetime.now(UTC)
    run = Run(
        run_id="sum-run-2",
        agent_id="agent",
        environment=Environment.DEVELOPMENT,
        status=RunStatus.RUNNING,
        created_at=now,
        updated_at=now,
    )
    storage.create_run(run)
    storage.append_event(RuntimeEvent(
        event_id="evt-1", run_id="sum-run-2",
        event_type=RuntimeEventType.RUN_STARTED,
        timestamp=now,
    ))

    summary = build_run_summary(storage, "sum-run-2")

    assert summary.run_id == "sum-run-2"
    assert summary.status == "running"
    assert summary.event_count == 1
    assert summary.decision_counts == {}
    assert summary.blocked_count == 0
    assert summary.review_count == 0
    assert summary.started_at is not None
    assert summary.completed_at is None


def test_run_summary_multiple_decision_types(tmp_path):
    storage = SQLiteStorage(tmp_path / "test.sqlite")
    storage.init()
    now = datetime.now(UTC)
    run = Run(
        run_id="sum-run-3",
        agent_id="agent",
        environment=Environment.DEVELOPMENT,
        status=RunStatus.REQUIRES_REVIEW,
        created_at=now,
        updated_at=now,
    )
    storage.create_run(run)
    storage.append_event(RuntimeEvent(
        event_id="evt-1", run_id="sum-run-3",
        event_type=RuntimeEventType.RUN_STARTED,
        timestamp=now,
    ))
    for i, decision in enumerate(("allow", "warn", "block", "require_review", "sanitize", "allow")):
        storage.append_event(RuntimeEvent(
            event_id=f"evt-dec-{i}", run_id="sum-run-3",
            event_type=RuntimeEventType.GOVERNANCE_DECISION,
            timestamp=now, payload={"decision": decision},
        ))

    summary = build_run_summary(storage, "sum-run-3")

    assert summary.event_count == 7
    assert summary.decision_counts == {
        "allow": 2, "warn": 1, "block": 1,
        "require_review": 1, "sanitize": 1,
    }
    assert summary.blocked_count == 1
    assert summary.review_count == 1
    assert summary.metadata_version == "1"


def test_run_summary_missing_run_raises_not_found(tmp_path):
    storage = SQLiteStorage(tmp_path / "test.sqlite")
    storage.init()
    import pytest
    with pytest.raises(AilurosNotFoundError):
        build_run_summary(storage, "nonexistent-run")
