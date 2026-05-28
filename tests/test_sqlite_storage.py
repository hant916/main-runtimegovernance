import concurrent.futures
from datetime import UTC, datetime

import pytest

from ailuros.errors import AilurosDataCorruptionError
from ailuros.models import (
    AuditReport,
    Environment,
    EvaluationResult,
    GovernanceDecision,
    GovernanceDecisionType,
    ReplayResult,
    Run,
    RunStatus,
    RuntimeEvent,
    RuntimeEventType,
    Severity,
    Step,
    StepStatus,
    StepType,
)
from ailuros.storage import SQLiteStorage


def test_storage_round_trips_records(tmp_path):
    storage = SQLiteStorage(tmp_path / "runtime.sqlite")
    storage.init()
    now = datetime.now(UTC)
    run = Run(
        run_id="run_1",
        agent_id="agent",
        environment=Environment.DEVELOPMENT,
        status=RunStatus.RUNNING,
        input={"prompt": "hi"},
        created_at=now,
        updated_at=now,
    )
    storage.create_run(run)
    step = Step(
        step_id="step_1",
        run_id=run.run_id,
        step_type=StepType.TOOL,
        status=StepStatus.STARTED,
        created_at=now,
        updated_at=now,
    )
    storage.create_step(step)
    first = storage.append_event(
        RuntimeEvent(
            event_id="evt_1",
            run_id=run.run_id,
            event_type=RuntimeEventType.RUN_STARTED,
            timestamp=now,
            payload={"a": 1},
        )
    )
    second = storage.append_event(
        RuntimeEvent(
            event_id="evt_2",
            run_id=run.run_id,
            event_type=RuntimeEventType.RUN_COMPLETED,
            timestamp=now,
            payload={"b": 2},
        )
    )
    storage.save_governance_decision(
        GovernanceDecision(
            decision_id="dec_1",
            run_id=run.run_id,
            decision=GovernanceDecisionType.ALLOW,
            allowed=True,
            reason="ok",
            severity=Severity.LOW,
            created_at=now,
        )
    )
    storage.save_evaluation(
        EvaluationResult(
            evaluation_id="eval_1",
            run_id=run.run_id,
            evaluator="test",
            passed=True,
            created_at=now,
        )
    )
    storage.save_audit_report(AuditReport(audit_id="audit_1", run_id=run.run_id, created_at=now))
    storage.save_replay_result(
        ReplayResult(replay_id="replay_1", run_id=run.run_id, status="completed", created_at=now)
    )

    assert first.sequence == 1
    assert second.sequence == 2
    assert storage.get_run(run.run_id).input == {"prompt": "hi"}
    assert storage.get_step(step.step_id).step_type is StepType.TOOL
    assert [event.sequence for event in storage.list_events(run.run_id)] == [1, 2]


def test_concurrent_event_append_same_run_produces_unique_sequences(tmp_path):
    storage = SQLiteStorage(tmp_path / "concurrent.sqlite")
    storage.init()
    now = datetime.now(UTC)
    run = Run(
        run_id="concurrent_run",
        agent_id="agent",
        environment=Environment.DEVELOPMENT,
        status=RunStatus.RUNNING,
        created_at=now,
        updated_at=now,
    )
    storage.create_run(run)

    n = 20
    with concurrent.futures.ThreadPoolExecutor(max_workers=n) as executor:
        futures = [
            executor.submit(
                storage.append_event,
                RuntimeEvent(
                    event_id=f"concurrent_evt_{i}",
                    run_id=run.run_id,
                    event_type=RuntimeEventType.RUN_STARTED,
                    timestamp=now,
                    payload={"i": i},
                ),
            )
            for i in range(n)
        ]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    sequences = [r.sequence for r in results]
    assert len(sequences) == n
    assert len(set(sequences)) == n, f"Duplicate sequences: {sequences}"

    evts = storage.list_events(run.run_id)
    assert [e.sequence for e in evts] == sorted(sequences)


def _make_run_for_storage(storage, run_id: str):
    run = Run(
        run_id=run_id,
        agent_id="agent",
        environment=Environment.DEVELOPMENT,
        status=RunStatus.COMPLETED,
        input={"prompt": run_id},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    storage.create_run(run)


class TestListRunsPagination:
    def test_default_returns_all(self, tmp_path):
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        for i in range(5):
            _make_run_for_storage(storage, f"run_{i}")
        result = storage.list_runs()
        assert len(result) == 5

    def test_limit(self, tmp_path):
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        for i in range(5):
            _make_run_for_storage(storage, f"run_{i}")
        result = storage.list_runs(limit=2)
        assert len(result) == 2

    def test_offset(self, tmp_path):
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        for i in range(5):
            _make_run_for_storage(storage, f"run_{i}")
        result = storage.list_runs(offset=3)
        assert len(result) == 2

    def test_limit_with_offset(self, tmp_path):
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        for i in range(5):
            _make_run_for_storage(storage, f"run_{i}")
        result = storage.list_runs(limit=2, offset=2)
        assert len(result) == 2


class TestListEventsPagination:
    def test_default_returns_all(self, tmp_path):
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run_for_storage(storage, "run_1")
        now = datetime.now(UTC)
        for i in range(5):
            storage.append_event(
                RuntimeEvent(
                    event_id=f"evt_{i}", run_id="run_1",
                    event_type=RuntimeEventType.RUN_STARTED,
                    timestamp=now, payload={"i": i},
                )
            )
        result = storage.list_events("run_1")
        assert len(result) == 5

    def test_limit(self, tmp_path):
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run_for_storage(storage, "run_1")
        now = datetime.now(UTC)
        for i in range(5):
            storage.append_event(
                RuntimeEvent(
                    event_id=f"evt_{i}", run_id="run_1",
                    event_type=RuntimeEventType.RUN_STARTED,
                    timestamp=now, payload={"i": i},
                )
            )
        result = storage.list_events("run_1", limit=2)
        assert len(result) == 2

    def test_offset(self, tmp_path):
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run_for_storage(storage, "run_1")
        now = datetime.now(UTC)
        for i in range(5):
            storage.append_event(
                RuntimeEvent(
                    event_id=f"evt_{i}", run_id="run_1",
                    event_type=RuntimeEventType.RUN_STARTED,
                    timestamp=now, payload={"i": i},
                )
            )
        result = storage.list_events("run_1", offset=3)
        assert len(result) == 2
        assert result[0].sequence == 4

    def test_limit_with_offset(self, tmp_path):
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run_for_storage(storage, "run_1")
        now = datetime.now(UTC)
        for i in range(5):
            storage.append_event(
                RuntimeEvent(
                    event_id=f"evt_{i}", run_id="run_1",
                    event_type=RuntimeEventType.RUN_STARTED,
                    timestamp=now, payload={"i": i},
                )
            )
        result = storage.list_events("run_1", limit=2, offset=2)
        assert len(result) == 2
        assert result[0].sequence == 3


class TestListEvaluationsPagination:
    def test_default_returns_all(self, tmp_path):
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run_for_storage(storage, "run_1")
        now = datetime.now(UTC)
        for i in range(5):
            storage.save_evaluation(
                EvaluationResult(
                    evaluation_id=f"eval_{i}", run_id="run_1",
                    evaluator="test", passed=True,
                    created_at=now,
                )
            )
        result = storage.list_evaluations()
        assert len(result) == 5

    def test_limit(self, tmp_path):
        storage = SQLiteStorage(tmp_path / "test.sqlite")
        storage.init()
        _make_run_for_storage(storage, "run_1")
        now = datetime.now(UTC)
        for i in range(5):
            storage.save_evaluation(
                EvaluationResult(
                    evaluation_id=f"eval_{i}", run_id="run_1",
                    evaluator="test", passed=True,
                    created_at=now,
                )
            )
        result = storage.list_evaluations(limit=2)
        assert len(result) == 2


def test_init_is_idempotent(tmp_path):
    storage = SQLiteStorage(tmp_path / "idempotent.sqlite")
    storage.init()
    storage.init()
    _make_run_for_storage(storage, "run_idem")
    assert storage.get_run("run_idem").run_id == "run_idem"


def test_corrupt_json_raises_explicit_error(tmp_path):
    storage = SQLiteStorage(tmp_path / "runtime.sqlite")
    storage.init()
    storage._connect().execute(  # noqa: SLF001
        "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "run_bad",
            "agent",
            "development",
            "running",
            None,
            None,
            "{bad",
            datetime.now(UTC).isoformat(),
            datetime.now(UTC).isoformat(),
        ),
    )

    with pytest.raises(AilurosDataCorruptionError):
        storage.get_run("run_bad")
