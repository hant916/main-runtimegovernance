"""Prove exact-event-id import idempotency and rebuild idempotency.

Pack 8077: lock-import-and-rebuild-idempotency.

The canonical production-derived fixture is
`fixtures/runtime-evidence/everrun-postfix-minimal/` (run id
`run-20260824-004751`), the privacy-screened minimal distillation of the
accepted 8065/8066 raw EverRun evidence. The second-producer fixture
(`fixtures/runtime-evidence/second-producer/`) carries a non-empty signal set
(`authority_violation`) and is used to prove rebuild stability where derived
signals are present.

Red lines honored here:
- Exact event ids are never collapsed: after repeated import the stored ids are
  exactly the package ids, each present exactly once.
- Conflict detection is not weakened: the same event_id with different content
  returns `CONFLICT` and the original stored content is preserved.
- Source packages are never mutated: the conflict case uses an in-memory
  deep copy only; the on-disk fixture is never written.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ailuros.adapters.evidence_package import (
    ImportStatus,
    ingest_evidence_package,
    load_evidence_package,
)
from ailuros.execution_report import (
    build_governed_execution_result,
    build_run_report,
)
from ailuros.projection import rebuild_projections_and_signals
from ailuros.storage.sqlite_storage import SQLiteStorage

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
EVERRUN_FIXTURE = (
    REPO_ROOT / "fixtures" / "runtime-evidence" / "everrun-postfix-minimal"
)
SECOND_FIXTURE = REPO_ROOT / "fixtures" / "runtime-evidence" / "second-producer"

EVERRUN_RUN_ID = "run-20260824-004751"
SECOND_RUN_ID = "run-second-producer-001"


def _new_storage(tmp_path: Path, name: str) -> SQLiteStorage:
    storage = SQLiteStorage(tmp_path / f"{name}.db")
    storage.init()
    return storage


def _signal_shape(signals) -> list[tuple]:
    return sorted(
        (
            s.type,
            s.severity,
            s.subject,
            sorted(ref.event_id for ref in s.evidence_refs),
        )
        for s in signals
    )


def _stored_signals_without_created(rows: list[dict]) -> list[dict]:
    return [{k: v for k, v in row.items() if k != "created_at"} for row in rows]


# ── T1: repeated import of the identical package is idempotent ───────────────


def test_repeated_import_of_canonical_package_is_idempotent(tmp_path) -> None:
    package = load_evidence_package(EVERRUN_FIXTURE)
    storage = _new_storage(tmp_path, "import-everrun")

    first = ingest_evidence_package(storage, package)
    assert first.status == ImportStatus.CREATED
    assert first.events_imported == len(package.events) == 5
    assert first.events_skipped == 0

    second = ingest_evidence_package(storage, package)
    assert second.status == ImportStatus.ALREADY_PRESENT
    assert second.events_imported == 0
    assert second.events_skipped == len(package.events) == 5

    stored = storage.list_events(EVERRUN_RUN_ID)
    assert len(stored) == len(package.events)
    assert {e.event_id for e in stored} == {e.event_id for e in package.events}
    assert len({e.event_id for e in stored}) == len(stored)


def test_repeated_import_is_idempotent_for_second_producer(tmp_path) -> None:
    package = load_evidence_package(SECOND_FIXTURE)
    storage = _new_storage(tmp_path, "import-second")

    first = ingest_evidence_package(storage, package)
    assert first.status == ImportStatus.CREATED
    assert first.events_imported == len(package.events) == 6

    second = ingest_evidence_package(storage, package)
    assert second.status == ImportStatus.ALREADY_PRESENT
    assert second.events_imported == 0
    assert second.events_skipped == len(package.events) == 6

    stored = storage.list_events(SECOND_RUN_ID)
    assert len(stored) == len(package.events)
    assert len({e.event_id for e in stored}) == len(stored)


def test_repeated_import_does_not_change_stored_content(tmp_path) -> None:
    """ALREADY_PRESENT must be a no-op on the stored raw evidence: the same
    event ids, sequences, and payloads as after the first import."""
    package = load_evidence_package(EVERRUN_FIXTURE)
    storage = _new_storage(tmp_path, "noop")

    ingest_evidence_package(storage, package)
    after_first = [
        (e.event_id, e.sequence, e.payload) for e in storage.list_events(EVERRUN_RUN_ID)
    ]

    assert ingest_evidence_package(storage, package).status == ImportStatus.ALREADY_PRESENT
    after_second = [
        (e.event_id, e.sequence, e.payload) for e in storage.list_events(EVERRUN_RUN_ID)
    ]
    assert after_second == after_first


# ── T2: repeated rebuild is idempotent ───────────────────────────────────────


@pytest.mark.parametrize(
    ("fixture", "run_id"),
    [
        (EVERRUN_FIXTURE, EVERRUN_RUN_ID),
        (SECOND_FIXTURE, SECOND_RUN_ID),
    ],
)
def test_repeated_rebuild_is_idempotent_across_canonical_fixtures(
    tmp_path: Path,
    fixture: Path,
    run_id: str,
) -> None:
    package = load_evidence_package(fixture)
    storage = _new_storage(tmp_path, f"rebuild-{run_id}")
    ingest_evidence_package(storage, package)

    proj1, signals1 = rebuild_projections_and_signals(storage, run_id)
    proj2, signals2 = rebuild_projections_and_signals(storage, run_id)

    assert proj1.model_dump() == proj2.model_dump()
    assert _signal_shape(signals1) == _signal_shape(signals2)

    stored1 = storage.get_projection(run_id)
    stored2 = storage.get_projection(run_id)
    assert stored1 is not None and stored2 is not None
    assert stored1["projection"] == stored2["projection"]

    assert _stored_signals_without_created(
        storage.get_signals(run_id)
    ) == _stored_signals_without_created(storage.get_signals(run_id))

    refs1 = sorted(ref.event_id for ref in proj1.evidence_refs)
    refs2 = sorted(ref.event_id for ref in proj2.evidence_refs)
    assert refs1 == refs2
    ids = {e.event_id for e in storage.list_events(run_id)}
    assert set(refs1) <= ids

    report1 = build_run_report(proj1, signals1)
    report2 = build_run_report(proj2, signals2)
    assert report1.model_dump() == report2.model_dump()

    result1 = build_governed_execution_result(proj1, signals1)
    result2 = build_governed_execution_result(proj2, signals2)
    assert result1.model_dump() == result2.model_dump()


def test_rebuild_signals_are_non_empty_and_stable_for_second_producer(
    tmp_path,
) -> None:
    """The second-producer fixture must yield derived signals; rebuild twice and
    pin their identity (type/severity/subject/evidence refs) as stable."""
    package = load_evidence_package(SECOND_FIXTURE)
    storage = _new_storage(tmp_path, "signals-second")
    ingest_evidence_package(storage, package)

    _, signals1 = rebuild_projections_and_signals(storage, SECOND_RUN_ID)
    _, signals2 = rebuild_projections_and_signals(storage, SECOND_RUN_ID)

    assert signals1, "second-producer fixture must yield signals for this proof"
    assert {s.type for s in signals1} == {"authority_violation"}
    assert _signal_shape(signals1) == _signal_shape(signals2)


# ── T3: conflict semantics are preserved, not silently absorbed ──────────────


def test_same_event_id_conflicting_content_returns_conflict_not_absorbed(
    tmp_path,
) -> None:
    package = load_evidence_package(EVERRUN_FIXTURE)
    storage = _new_storage(tmp_path, "conflict-first")
    assert ingest_evidence_package(storage, package).status == ImportStatus.CREATED

    conflicting = package.model_copy(deep=True)
    first_event = conflicting.events[0]
    conflicting.events[0] = first_event.model_copy(
        update={"payload": {**first_event.payload, "agent": "mutated-content"}}
    )

    result = ingest_evidence_package(storage, conflicting)
    assert result.status == ImportStatus.CONFLICT
    assert result.status != ImportStatus.ALREADY_PRESENT

    stored = storage.list_events(EVERRUN_RUN_ID)
    assert len(stored) == len(package.events)
    original = next(e for e in stored if e.event_id == package.events[0].event_id)
    assert original.payload["payload"]["agent"] == "codex"
    assert original.payload["payload"]["agent"] != "mutated-content"


def test_conflict_detected_even_when_only_last_event_differs(tmp_path) -> None:
    """A conflict anywhere in the package must not be silently absorbed as an
    idempotent re-import even when every preceding event is an exact-id match."""
    package = load_evidence_package(EVERRUN_FIXTURE)
    storage = _new_storage(tmp_path, "conflict-last")
    assert ingest_evidence_package(storage, package).status == ImportStatus.CREATED

    conflicting = package.model_copy(deep=True)
    last_event = conflicting.events[-1]
    conflicting.events[-1] = last_event.model_copy(
        update={"payload": {**last_event.payload, "status": "violated"}}
    )

    result = ingest_evidence_package(storage, conflicting)
    assert result.status == ImportStatus.CONFLICT
    assert result.events_skipped == len(package.events) - 1
    assert result.events_imported == 0

    stored = storage.list_events(EVERRUN_RUN_ID)
    assert len(stored) == len(package.events)
    original_last = next(
        e for e in stored if e.event_id == package.events[-1].event_id
    )
    assert original_last.payload["payload"]["status"] == "clean"
