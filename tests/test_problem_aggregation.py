from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from ailuros.core.execution import EvidenceRef
from ailuros.models import Environment, Run, RunStatus
from ailuros.problems import (
    ProblemDetail,
    ProblemGroup,
    aggregate_problems,
    get_problem_detail,
)
from ailuros.storage import SQLiteStorage


def _make_run(
    storage: SQLiteStorage,
    run_id: str,
    *,
    created_at: datetime | None = None,
) -> Run:
    now = created_at or datetime.now(UTC)
    run = Run(
        run_id=run_id,
        agent_id="agent-1",
        environment=Environment.DEVELOPMENT,
        status=RunStatus.COMPLETED,
        input={"prompt": "task"},
        created_at=now,
        updated_at=now,
    )
    storage.create_run(run)
    return run


def _insert_signal(
    storage: SQLiteStorage,
    run_id: str,
    *,
    signal_id: str | None = None,
    signal_type: str = "validation_failure",
    severity: str = "high",
    subject: str = "validation",
    evidence_refs: list[dict] | None = None,
    details: dict | None = None,
    created_at: datetime | None = None,
) -> dict:
    sid = signal_id or f"sig-{run_id}-{signal_type}"
    created = created_at or datetime.now(UTC)
    signal = {
        "signal_id": sid,
        "run_id": run_id,
        "type": signal_type,
        "severity": severity,
        "subject": subject,
        "evidence_refs": evidence_refs or [],
        "details": details or {},
        "created_at": created.isoformat(),
    }
    existing = storage.get_signals(run_id)
    for s in existing:
        if isinstance(s["created_at"], datetime):
            s["created_at"] = s["created_at"].isoformat()
    existing.append(signal)
    storage.replace_signals(run_id, existing)
    return signal


def _setup_storage(tmp_path: Path) -> SQLiteStorage:
    storage = SQLiteStorage(tmp_path / "test.sqlite")
    storage.init()
    return storage


# ── Empty / no-signal window ────────────────────────────────────────────


def test_aggregate_empty_no_signals(tmp_path: Path) -> None:
    storage = _setup_storage(tmp_path)
    result = aggregate_problems(storage)
    assert result == []


# ── Basic grouping across runs ──────────────────────────────────────────


def test_aggregate_groups_signals_by_type_and_subject(tmp_path: Path) -> None:
    storage = _setup_storage(tmp_path)
    now = datetime.now(UTC)

    _make_run(storage, "run-a", created_at=now)
    _make_run(storage, "run-b", created_at=now)

    _insert_signal(
        storage, "run-a",
        signal_type="validation_failure",
        subject="validation", severity="high", created_at=now,
    )
    _insert_signal(
        storage, "run-b",
        signal_type="validation_failure",
        subject="validation", severity="high",
        created_at=now + timedelta(hours=1),
    )
    _insert_signal(
        storage, "run-a",
        signal_type="backend_fallback",
        subject="backend", severity="medium", created_at=now,
    )

    result = aggregate_problems(storage)
    assert len(result) == 2

    vf = result[0]
    assert vf.signal_type == "validation_failure"
    assert vf.subject_key == "validation"
    assert vf.count == 2
    assert set(vf.affected_run_ids) == {"run-a", "run-b"}
    assert vf.severity_counts == {"high": 2}

    bf = result[1]
    assert bf.signal_type == "backend_fallback"
    assert bf.subject_key == "backend"
    assert bf.count == 1
    assert bf.affected_run_ids == ["run-a"]


# ── Stable ordering by count then last_seen ─────────────────────────────


def test_aggregate_orders_by_count_desc_then_last_seen_desc(
    tmp_path: Path,
) -> None:
    storage = _setup_storage(tmp_path)
    now = datetime.now(UTC)

    _make_run(storage, "r1", created_at=now)
    _make_run(storage, "r2", created_at=now)
    _make_run(storage, "r3", created_at=now)

    _insert_signal(
        storage, "r1", signal_type="type-a", subject="subj", created_at=now,
    )
    _insert_signal(
        storage, "r2", signal_type="type-a", subject="subj",
        created_at=now + timedelta(hours=1),
    )
    _insert_signal(
        storage, "r3", signal_type="type-a", subject="subj",
        created_at=now + timedelta(hours=2),
    )

    _insert_signal(
        storage, "r1", signal_type="type-b", subject="subj",
        severity="medium", created_at=now + timedelta(hours=3),
    )
    _insert_signal(
        storage, "r2", signal_type="type-b", subject="subj",
        severity="low", created_at=now + timedelta(hours=4),
    )

    result = aggregate_problems(storage)
    assert len(result) == 2
    assert result[0].signal_type == "type-a"
    assert result[0].count == 3
    assert result[1].signal_type == "type-b"
    assert result[1].count == 2


# ── Trend buckets ───────────────────────────────────────────────────────


def test_aggregate_builds_daily_trend_buckets(tmp_path: Path) -> None:
    storage = _setup_storage(tmp_path)
    day1 = datetime(2025, 6, 1, 10, 0, 0, tzinfo=UTC)
    day2 = datetime(2025, 6, 2, 14, 0, 0, tzinfo=UTC)
    day4 = datetime(2025, 6, 4, 9, 0, 0, tzinfo=UTC)

    _make_run(storage, "r1", created_at=day1)
    _make_run(storage, "r2", created_at=day2)
    _make_run(storage, "r3", created_at=day4)

    _insert_signal(
        storage, "r1", signal_type="test", subject="x", created_at=day1,
    )
    _insert_signal(
        storage, "r2", signal_type="test", subject="x", created_at=day2,
    )
    _insert_signal(
        storage, "r3", signal_type="test", subject="x", created_at=day4,
    )

    result = aggregate_problems(storage)
    assert len(result) == 1
    group = result[0]
    assert len(group.trend_buckets) == 4
    labels = [b.label for b in group.trend_buckets]
    assert labels == [
        "2025-06-01", "2025-06-02", "2025-06-03", "2025-06-04",
    ]
    counts = [b.count for b in group.trend_buckets]
    assert counts == [1, 1, 0, 1]


# ── Severity counts ─────────────────────────────────────────────────────


def test_aggregate_tracks_severity_counts(tmp_path: Path) -> None:
    storage = _setup_storage(tmp_path)
    now = datetime.now(UTC)

    _make_run(storage, "r1", created_at=now)
    _make_run(storage, "r2", created_at=now)
    _make_run(storage, "r3", created_at=now)

    _insert_signal(
        storage, "r1", signal_type="t", subject="s",
        severity="high", created_at=now,
    )
    _insert_signal(
        storage, "r2", signal_type="t", subject="s",
        severity="high", created_at=now + timedelta(minutes=1),
    )
    _insert_signal(
        storage, "r3", signal_type="t", subject="s",
        severity="medium", created_at=now + timedelta(minutes=2),
    )

    result = aggregate_problems(storage)
    assert len(result) == 1
    assert result[0].severity_counts == {"high": 2, "medium": 1}


# ── Drill-down returns contributing signals ─────────────────────────────


def test_get_problem_detail_returns_contributing_signals(
    tmp_path: Path,
) -> None:
    storage = _setup_storage(tmp_path)
    now = datetime.now(UTC)

    _make_run(storage, "r1", created_at=now)
    _make_run(storage, "r2", created_at=now)

    refs = [{"event_id": "evt-1", "artifact": None, "pointer": None}]
    _insert_signal(
        storage, "r1", signal_id="sig-001",
        signal_type="validation_failure", subject="validation",
        evidence_refs=refs, created_at=now,
    )
    _insert_signal(
        storage, "r2", signal_id="sig-002",
        signal_type="validation_failure", subject="validation",
        evidence_refs=[], created_at=now + timedelta(hours=1),
    )

    detail = get_problem_detail(storage, "validation_failure", "validation")
    assert isinstance(detail, ProblemDetail)
    assert detail.signal_type == "validation_failure"
    assert detail.subject_key == "validation"
    assert detail.group.count == 2
    assert len(detail.contributing_signals) == 2
    assert detail.contributing_signals[0].signal_id == "sig-001"
    assert detail.contributing_signals[0].run_id == "r1"
    assert len(detail.contributing_signals[0].evidence_refs) == 1
    ref0 = detail.contributing_signals[0].evidence_refs[0]
    assert isinstance(ref0, EvidenceRef)
    assert ref0.event_id == "evt-1"
    assert detail.contributing_signals[1].signal_id == "sig-002"


def test_get_problem_detail_raises_on_unknown_group(tmp_path: Path) -> None:
    storage = _setup_storage(tmp_path)
    _make_run(storage, "r1")
    _insert_signal(storage, "r1", signal_type="t", subject="s")
    try:
        get_problem_detail(storage, "unknown_type", "unknown_subject")
        raise AssertionError("expected LookupError")
    except LookupError:
        pass


# ── Time filtering ──────────────────────────────────────────────────────


def test_aggregate_filters_by_time_window(tmp_path: Path) -> None:
    storage = _setup_storage(tmp_path)
    t1 = datetime(2025, 1, 1, tzinfo=UTC)
    t2 = datetime(2025, 1, 10, tzinfo=UTC)
    t3 = datetime(2025, 1, 20, tzinfo=UTC)

    _make_run(storage, "r1", created_at=t1)
    _make_run(storage, "r2", created_at=t2)
    _make_run(storage, "r3", created_at=t3)

    _insert_signal(
        storage, "r1", signal_type="t", subject="s", created_at=t1,
    )
    _insert_signal(
        storage, "r2", signal_type="t", subject="s", created_at=t2,
    )
    _insert_signal(
        storage, "r3", signal_type="t", subject="s", created_at=t3,
    )

    all_result = aggregate_problems(storage)
    assert all_result[0].count == 3

    filtered = aggregate_problems(
        storage, window_start=datetime(2025, 1, 5, tzinfo=UTC),
    )
    assert filtered[0].count == 2

    narrow = aggregate_problems(
        storage,
        window_start=datetime(2025, 1, 5, tzinfo=UTC),
        window_end=datetime(2025, 1, 15, tzinfo=UTC),
    )
    assert narrow[0].count == 1


# ── Repeated validation failure across runs ─────────────────────────────


def test_repeated_validation_failure_across_runs(tmp_path: Path) -> None:
    storage = _setup_storage(tmp_path)
    now = datetime.now(UTC)

    for i in range(5):
        run_id = f"run-{i}"
        _make_run(storage, run_id, created_at=now + timedelta(hours=i))
        _insert_signal(
            storage, run_id,
            signal_type="repeated_validation_failure",
            subject="repeated_validation",
            severity="high",
            created_at=now + timedelta(hours=i),
        )

    result = aggregate_problems(storage)
    assert len(result) == 1
    assert result[0].signal_type == "repeated_validation_failure"
    assert result[0].subject_key == "repeated_validation"
    assert result[0].count == 5
    assert len(result[0].affected_run_ids) == 5


# ── Backend fallback across roles/providers ─────────────────────────────


def test_backend_fallback_aggregation(tmp_path: Path) -> None:
    storage = _setup_storage(tmp_path)
    now = datetime.now(UTC)

    _make_run(storage, "run-role-a", created_at=now)
    _make_run(storage, "run-role-b", created_at=now)
    _make_run(storage, "run-provider-x", created_at=now)

    _insert_signal(
        storage, "run-role-a",
        signal_type="backend_fallback", subject="backend",
        severity="medium", details={"role": "coder"},
        created_at=now,
    )
    _insert_signal(
        storage, "run-role-b",
        signal_type="backend_fallback", subject="backend",
        severity="medium", details={"role": "planner"},
        created_at=now + timedelta(minutes=1),
    )
    _insert_signal(
        storage, "run-provider-x",
        signal_type="backend_fallback", subject="backend",
        severity="low", details={"provider": "openai"},
        created_at=now + timedelta(minutes=2),
    )

    result = aggregate_problems(storage)
    assert len(result) == 1
    g = result[0]
    assert g.signal_type == "backend_fallback"
    assert g.subject_key == "backend"
    assert g.count == 3
    assert set(g.affected_run_ids) == {
        "run-role-a", "run-role-b", "run-provider-x",
    }
    assert g.severity_counts == {"medium": 2, "low": 1}


# ── ProblemGroup model validation ───────────────────────────────────────


def test_problem_group_fields_match_spec(tmp_path: Path) -> None:
    storage = _setup_storage(tmp_path)
    now = datetime.now(UTC)
    _make_run(storage, "r1", created_at=now)
    _insert_signal(
        storage, "r1",
        signal_type="validation_failure",
        subject="validation", severity="critical", created_at=now,
    )

    groups = aggregate_problems(storage)
    g = groups[0]
    assert isinstance(g, ProblemGroup)
    assert isinstance(g.signal_type, str)
    assert isinstance(g.subject_key, str)
    assert isinstance(g.count, int)
    assert isinstance(g.affected_run_ids, list)
    assert isinstance(g.first_seen, datetime)
    assert isinstance(g.last_seen, datetime)
    assert isinstance(g.severity_counts, dict)
    assert isinstance(g.trend_buckets, list)
    assert g.first_seen.tzinfo is not None
    assert g.last_seen.tzinfo is not None


# ── Backend unavailable across runs ─────────────────────────────────────


def test_backend_unavailable_aggregation(tmp_path: Path) -> None:
    storage = _setup_storage(tmp_path)
    now = datetime.now(UTC)

    for i in range(3):
        rid = f"r-{i}"
        _make_run(storage, rid, created_at=now + timedelta(hours=i))
        _insert_signal(
            storage, rid,
            signal_type="backend_unavailable", subject="backend",
            severity="high", created_at=now + timedelta(hours=i),
        )

    result = aggregate_problems(storage)
    assert len(result) == 1
    assert result[0].signal_type == "backend_unavailable"
    assert result[0].count == 3
    assert result[0].severity_counts == {"high": 3}


# ── Multiple signal types coexist ───────────────────────────────────────


def test_multiple_signal_types_with_different_subjects(tmp_path: Path) -> None:
    storage = _setup_storage(tmp_path)
    now = datetime.now(UTC)

    _make_run(storage, "r1", created_at=now)
    _insert_signal(
        storage, "r1",
        signal_type="validation_failure", subject="validation",
        created_at=now,
    )
    _insert_signal(
        storage, "r1",
        signal_type="scope_violation", subject="scope",
        severity="critical", created_at=now,
    )
    _insert_signal(
        storage, "r1",
        signal_type="backend_fallback", subject="backend",
        created_at=now,
    )

    result = aggregate_problems(storage)
    assert len(result) == 3
    types = {g.signal_type for g in result}
    assert types == {"validation_failure", "scope_violation", "backend_fallback"}
