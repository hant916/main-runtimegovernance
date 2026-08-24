from __future__ import annotations

import json
import shutil
from pathlib import Path

from ailuros.adapters.evidence_package import (
    ImportStatus,
    ingest_evidence_package,
    load_evidence_package,
    validate_evidence_package_contract,
)
from ailuros.execution_report import build_run_report
from ailuros.projection import build_execution_projection, rebuild_projections_and_signals
from ailuros.storage.sqlite_storage import SQLiteStorage

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures" / "evidence_package"
VALID_V1 = FIXTURES / "valid-v1"
EVERRUN_POSTFIX_MINIMAL = (
    HERE.parent / "fixtures" / "runtime-evidence" / "everrun-postfix-minimal"
)


def _new_storage(tmp_path: Path) -> SQLiteStorage:
    db_path = tmp_path / "test.db"
    storage = SQLiteStorage(db_path)
    storage.init()
    return storage


def _copy_and_load_fixture(tmp_path: Path, fixture: Path = VALID_V1) -> Path:
    dest = tmp_path / "pkg"
    shutil.copytree(fixture, dest)
    return dest


def test_first_import_stores_run_and_events(tmp_path):
    pkg_path = _copy_and_load_fixture(tmp_path)
    storage = _new_storage(tmp_path)
    package = load_evidence_package(pkg_path)

    result = ingest_evidence_package(storage, package)

    assert result.status == ImportStatus.CREATED
    assert result.run_id == "run-v1-001"
    assert result.events_imported == 2
    assert result.events_skipped == 0

    stored_run = storage.get_run("run-v1-001")
    assert stored_run.agent_id == "sample-agent-v1"
    assert stored_run.status == "completed"

    events = storage.list_events("run-v1-001")
    assert len(events) == 2
    assert events[0].event_id == "evt-v1-001"
    assert events[1].event_id == "evt-v1-002"
    assert all(e.event_type.value == "external_evidence" for e in events)


def test_second_identical_import_does_not_increase_counts(tmp_path):
    pkg_path = _copy_and_load_fixture(tmp_path)
    storage = _new_storage(tmp_path)
    package = load_evidence_package(pkg_path)

    first = ingest_evidence_package(storage, package)
    assert first.status == ImportStatus.CREATED
    assert first.events_imported == 2

    second = ingest_evidence_package(storage, package)
    assert second.status == ImportStatus.ALREADY_PRESENT
    assert second.events_imported == 0
    assert second.events_skipped == 2

    events = storage.list_events("run-v1-001")
    assert len(events) == 2


def test_changed_same_run_package_produces_conflict(tmp_path):
    pkg_path = _copy_and_load_fixture(tmp_path)
    storage = _new_storage(tmp_path)
    package = load_evidence_package(pkg_path)

    first = ingest_evidence_package(storage, package)
    assert first.status == ImportStatus.CREATED

    timeline = json.loads((pkg_path / "timeline.json").read_text(encoding="utf-8"))
    timeline["events"][0]["payload"] = {"input": "changed payload"}
    (pkg_path / "timeline.json").write_text(json.dumps(timeline), encoding="utf-8")

    changed_package = load_evidence_package(pkg_path)
    result = ingest_evidence_package(storage, changed_package)
    assert result.status == ImportStatus.CONFLICT
    assert result.run_id == "run-v1-001"


def test_import_preserves_run_metadata(tmp_path):
    pkg_path = _copy_and_load_fixture(tmp_path)
    storage = _new_storage(tmp_path)
    package = load_evidence_package(pkg_path)

    ingest_evidence_package(storage, package)
    stored_run = storage.get_run("run-v1-001")
    assert stored_run.metadata.get("imported_from_package") is True
    assert stored_run.metadata.get("source") == "sample-agent-v1"
    assert stored_run.metadata.get("schema_version") == "ailuros.timeline.v1"


def test_imported_events_project_semantics_without_mutating_raw_wrappers(tmp_path):
    pkg_path = _copy_and_load_fixture(tmp_path)
    storage = _new_storage(tmp_path)
    package = load_evidence_package(pkg_path)

    ingest_evidence_package(storage, package)
    projection, _ = rebuild_projections_and_signals(storage, package.run_id)

    assert projection.lifecycle.value == "completed"
    assert projection.outcome.value == "success"

    events = storage.list_events(package.run_id)
    assert all(event.event_type.value == "external_evidence" for event in events)
    assert events[0].payload == {
        "event_type": "run_started",
        "payload": {"input": "test v1 input"},
        "metadata": {},
    }


def test_malformed_external_evidence_wrappers_do_not_project_canonical_events():
    projection = build_execution_projection(
        run_id="run-malformed-wrapper-001",
        source="test",
        events=[
            {
                "event_id": "evt-malformed-payload",
                "event_type": "external_evidence",
                "payload": {"event_type": "run_completed", "payload": []},
            },
            {
                "event_id": "evt-missing-event-type",
                "event_type": "external_evidence",
                "payload": {"payload": {}},
            },
        ],
    )

    assert projection.lifecycle.value == "unknown"
    assert projection.outcome.value == "unknown"
    assert projection.event_count == 2


def test_import_result_includes_source_digest(tmp_path):
    from ailuros.core.evidence import EvidencePackage, PackageMetadata

    storage = _new_storage(tmp_path)
    package = EvidencePackage(
        source="test-source",
        schema_version="ailuros.timeline.v1",
        run_id="run-digest-001",
        pkg_metadata=PackageMetadata(source_digest="sha256:abc123"),
    )
    result = ingest_evidence_package(storage, package)
    assert result.source_digest == "sha256:abc123"

    stored_run = storage.get_run("run-digest-001")
    assert stored_run.metadata.get("imported_from_package") is True


def test_imported_scoped_event_scope_survives_ingest_and_projection(tmp_path):
    from datetime import UTC, datetime

    from ailuros.core.evidence import EvidenceEvent, EvidencePackage

    storage = _new_storage(tmp_path)
    package = EvidencePackage(
        source="test-source",
        schema_version="ailuros.timeline.v1",
        run_id="run-scoped-001",
        events=[
            EvidenceEvent(
                event_id="evt-scoped-1",
                event_type="run_started",
                timestamp=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
                payload={"input": "scoped input"},
                scope_ref="scope-abc",
            ),
            EvidenceEvent(
                event_id="evt-scoped-2",
                event_type="run_completed",
                timestamp=datetime(2025, 1, 15, 10, 1, 0, tzinfo=UTC),
                payload={"result": "completed"},
                scope_ref="scope-abc",
            ),
        ],
    )

    result = ingest_evidence_package(storage, package)
    assert result.status == ImportStatus.CREATED

    projection, _ = rebuild_projections_and_signals(storage, package.run_id)
    assert projection.scope_ref == "scope-abc"
    assert projection.run_id == "run-scoped-001"

    events = storage.list_events(package.run_id)
    assert all(e.event_type.value == "external_evidence" for e in events)
    assert events[0].payload["scope_ref"] == "scope-abc"
    assert events[0].payload["payload"] == {"input": "scoped input"}


def test_imported_unscoped_event_keeps_raw_wrapper_without_scope(tmp_path):
    from datetime import UTC, datetime

    from ailuros.core.evidence import EvidenceEvent, EvidencePackage

    storage = _new_storage(tmp_path)
    package = EvidencePackage(
        source="test-source",
        schema_version="ailuros.timeline.v1",
        run_id="run-unscoped-001",
        events=[
            EvidenceEvent(
                event_id="evt-unscoped-1",
                event_type="run_started",
                timestamp=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
                payload={"input": "plain input"},
            ),
            EvidenceEvent(
                event_id="evt-unscoped-2",
                event_type="run_completed",
                timestamp=datetime(2025, 1, 15, 10, 1, 0, tzinfo=UTC),
                payload={"result": "completed"},
            ),
        ],
    )

    ingest_evidence_package(storage, package)
    events = storage.list_events(package.run_id)
    assert "scope_ref" not in events[0].payload

    projection, _ = rebuild_projections_and_signals(storage, package.run_id)
    assert projection.scope_ref is None


def test_imported_scoped_event_reimport_is_idempotent(tmp_path):
    from datetime import UTC, datetime

    from ailuros.core.evidence import EvidenceEvent, EvidencePackage

    storage = _new_storage(tmp_path)
    package = EvidencePackage(
        source="test-source",
        schema_version="ailuros.timeline.v1",
        run_id="run-scoped-reimport-001",
        events=[
            EvidenceEvent(
                event_id="evt-scoped-re-1",
                event_type="run_started",
                timestamp=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
                payload={"input": "scoped input"},
                scope_ref="scope-re-1",
            ),
            EvidenceEvent(
                event_id="evt-scoped-re-2",
                event_type="run_completed",
                timestamp=datetime(2025, 1, 15, 10, 1, 0, tzinfo=UTC),
                payload={"result": "completed"},
                scope_ref="scope-re-1",
            ),
        ],
    )

    first = ingest_evidence_package(storage, package)
    assert first.status == ImportStatus.CREATED

    second = ingest_evidence_package(storage, package)
    assert second.status == ImportStatus.ALREADY_PRESENT
    assert second.events_skipped == 2

    events = storage.list_events(package.run_id)
    assert len(events) == 2
    assert events[0].payload["scope_ref"] == "scope-re-1"


def test_imported_scoped_timeline_loads_and_ingests(tmp_path):
    import json

    from ailuros.adapters.evidence_package import load_evidence_package

    pkg_path = _copy_and_load_fixture(tmp_path)
    timeline = json.loads((pkg_path / "timeline.json").read_text(encoding="utf-8"))
    timeline["events"][0]["scope_ref"] = "scope-timeline-1"
    (pkg_path / "timeline.json").write_text(json.dumps(timeline), encoding="utf-8")

    storage = _new_storage(tmp_path)
    package = load_evidence_package(pkg_path)
    assert package.events[0].scope_ref == "scope-timeline-1"

    result = ingest_evidence_package(storage, package)
    assert result.status == ImportStatus.CREATED

    projection, _ = rebuild_projections_and_signals(storage, package.run_id)
    assert projection.scope_ref == "scope-timeline-1"


def test_everrun_postfix_minimal_package_acceptance_regression(tmp_path):
    """8071: end-to-end regression on the 8070 production-derived fixture.

    Exercises the shared public pipeline validate -> load -> ingest -> rebuild ->
    governed result. Source-proven facts (validation/scope/decision-domain) must
    project determinately; facts the fixture carries no evidence for must stay
    unknown rather than being coerced to clean. All behavior is selected from
    evidence shape through shared functions, never from the producer name.
    """
    result = validate_evidence_package_contract(EVERRUN_POSTFIX_MINIMAL)
    assert result.ok is True
    assert result.errors == []
    assert result.source == "everrun"
    assert result.run_id == "run-20260824-004751"
    assert result.schema_version == "ailuros.timeline.v1"
    assert result.events_count == 5

    package = load_evidence_package(EVERRUN_POSTFIX_MINIMAL)
    assert package.source == "everrun"
    assert len(package.events) == 5

    storage = _new_storage(tmp_path)
    ingest_result = ingest_evidence_package(storage, package)
    assert ingest_result.status == ImportStatus.CREATED
    assert ingest_result.run_id == "run-20260824-004751"
    assert ingest_result.events_imported == 5
    assert ingest_result.events_skipped == 0

    projection, signals = rebuild_projections_and_signals(storage, package.run_id)
    report = build_run_report(projection, signals)

    assert projection.validation.value == "passed"
    assert projection.scope.value == "clean"
    assert [c.description for c in projection.changes] == [
        "docs/dogfood/everrun-history-baseline.md",
        "docs/operations/everrun-dogfood.md",
    ]
    assert projection.decision_count == 1
    assert [(d.domain, d.decision, d.projected_domain) for d in projection.decisions] == [
        ("execution_control", "human_review", "execution_control")
    ]
    assert projection.governance_coverage.validation.value == "evaluated"
    assert projection.governance_coverage.scope.value == "evaluated"
    assert report.validation == "passed"
    assert report.scope == "clean"
    assert report.decision_reasons == ["execution_control/human_review"]

    assert projection.lifecycle.value == "running"
    assert projection.outcome.value == "unknown"
    assert projection.governance_coverage.authority.value == "unknown"
    assert projection.governance_coverage.approval.value == "unknown"
    assert projection.governance_coverage.budget.value == "unknown"
    assert report.governed_outcome == "unknown"
    assert report.why_stopped == "execution_control: human_review"
    assert signals == []
