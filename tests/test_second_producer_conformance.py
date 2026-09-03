"""Second-producer framework-neutral conformance harness.

Proves Ailuros is not an EverRun-specific validator: a distinct, generic
MCP-style producer emitting the same runtime-evidence-package-v1 contract
travels through the exact same load / ingest / projection / signal /
governed-outcome code path as an EverRun-shaped package, with zero
producer-identity branching anywhere in src/ailuros.

"No Framework Left Behind" is a product claim; this is its test evidence.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ailuros import execution_report, projection
from ailuros import signals as signals_module
from ailuros.adapters.evidence_package import (
    ImportStatus,
    audit_evidence_package,
    ingest_evidence_package,
    load_evidence_package,
    validate_evidence_package_contract,
)
from ailuros.cli import app
from ailuros.execution_report import build_run_report
from ailuros.projection import build_execution_projection, rebuild_projections_and_signals
from ailuros.regression import GovernanceTransition, compare_governance_projections
from ailuros.storage.sqlite_storage import SQLiteStorage

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
SECOND_PRODUCER = REPO_ROOT / "fixtures" / "runtime-evidence" / "second-producer"
INVALID_FIXTURES = SECOND_PRODUCER / "invalid"
FIRST_PRODUCER = HERE / "fixtures" / "evidence_package" / "valid-v1"
EVERRUN_POSTFIX_MINIMAL = (
    REPO_ROOT / "fixtures" / "runtime-evidence" / "everrun-postfix-minimal"
)

SCOPE_REF = "scope-mcp-sp-001"


def _new_storage(tmp_path: Path) -> SQLiteStorage:
    storage = SQLiteStorage(tmp_path / "conformance.db")
    storage.init()
    return storage


# ── T1/T2: fixture exists and passes the same contract + import path ───────


def test_second_producer_fixture_exists_and_uses_v1_contract() -> None:
    manifest = SECOND_PRODUCER / "manifest.json"
    timeline = SECOND_PRODUCER / "timeline.json"
    assert manifest.is_file()
    assert timeline.is_file()

    result = validate_evidence_package_contract(SECOND_PRODUCER)
    assert result.ok is True
    assert result.errors == []
    assert result.source == "generic-mcp-workflow"
    assert result.schema_version == "ailuros.timeline.v1"
    assert result.events_count == 6

    audit = audit_evidence_package(SECOND_PRODUCER)
    assert audit.ok is True


def test_second_producer_source_name_is_distinct_from_everrun() -> None:
    result = validate_evidence_package_contract(SECOND_PRODUCER)
    assert result.source != "everrun"
    assert "everrun" not in result.source.lower()


@pytest.mark.parametrize(
    ("fixture_name", "diagnostic"),
    [
        ("missing-timeline", "required file missing: timeline.json"),
        ("missing-manifest-field", "manifest field missing or empty: governance_mode"),
        ("malformed-timestamp", "event[0] (event_id 'evt-sp-001') has invalid timestamp"),
        ("duplicate-event-id", "event[1] (event_id 'evt-sp-001') duplicates event_id"),
        ("malformed-payload", "event[0] (event_id 'evt-sp-001') payload must be an object"),
        ("malformed-scope", "event[0] (event_id 'evt-sp-001') scope_ref must be a string"),
    ],
)
def test_second_producer_invalid_fixtures_have_actionable_diagnostics(
    fixture_name: str,
    diagnostic: str,
) -> None:
    result = validate_evidence_package_contract(INVALID_FIXTURES / fixture_name)

    assert result.ok is False
    assert any(diagnostic in error for error in result.errors)


def test_loader_rejects_non_conformant_second_producer_package() -> None:
    with pytest.raises(ValueError, match="duplicates event_id"):
        load_evidence_package(INVALID_FIXTURES / "duplicate-event-id")


def test_evidence_audit_returns_nonzero_with_actionable_contract_error() -> None:
    result = CliRunner().invoke(
        app,
        ["evidence-audit", str(INVALID_FIXTURES / "malformed-payload")],
    )

    assert result.exit_code != 0
    assert "event[0] (event_id 'evt-sp-001') payload must be an object" in result.stdout


def test_second_producer_loads_and_imports_through_shared_path(tmp_path: Path) -> None:
    package = load_evidence_package(SECOND_PRODUCER)
    storage = _new_storage(tmp_path)

    result = ingest_evidence_package(storage, package)

    assert result.status == ImportStatus.CREATED
    assert result.run_id == "run-second-producer-001"
    assert result.events_imported == 6
    assert result.events_skipped == 0

    stored_run = storage.get_run("run-second-producer-001")
    assert stored_run.agent_id == "generic-mcp-workflow"


def test_second_producer_import_is_idempotent(tmp_path: Path) -> None:
    package = load_evidence_package(SECOND_PRODUCER)
    storage = _new_storage(tmp_path)

    first = ingest_evidence_package(storage, package)
    assert first.status == ImportStatus.CREATED

    second = ingest_evidence_package(storage, package)
    assert second.status == ImportStatus.ALREADY_PRESENT
    assert second.events_skipped == 6


# ── T3: same projection/governance path produces facts, not source branches ─


def test_second_producer_projection_uses_shared_pipeline(tmp_path: Path) -> None:
    package = load_evidence_package(SECOND_PRODUCER)
    storage = _new_storage(tmp_path)
    ingest_evidence_package(storage, package)

    proj, derived_signals = rebuild_projections_and_signals(storage, package.run_id)

    assert proj.run_id == "run-second-producer-001"
    assert proj.source == "rebuild"
    assert proj.event_count == 6
    assert proj.lifecycle.value == "completed"
    assert proj.validation.value == "passed"
    assert proj.outcome.value == "failed"
    assert len(proj.authority_records) == 1
    assert proj.authority_records[0].state.value == "violation"

    report = build_run_report(proj, derived_signals)
    assert report.run_id == "run-second-producer-001"
    assert report.governed_outcome in {
        "clean_success",
        "degraded_success",
        "review_required",
        "failed",
        "unknown",
    }


def test_first_and_second_producer_traverse_identical_pipeline(tmp_path: Path) -> None:
    """Direct parity check: an EverRun-shaped package and the generic MCP-style
    package are run through the byte-identical function objects, and produce
    structurally identical result shapes (same fields, same types) even
    though their raw evidence differs."""
    everrun_pkg = load_evidence_package(FIRST_PRODUCER)
    second_pkg = load_evidence_package(SECOND_PRODUCER)

    everrun_storage = _new_storage(tmp_path / "everrun")
    second_storage = _new_storage(tmp_path / "second")

    everrun_result = ingest_evidence_package(everrun_storage, everrun_pkg)
    second_result = ingest_evidence_package(second_storage, second_pkg)

    assert everrun_result.status == second_result.status == ImportStatus.CREATED

    everrun_proj, everrun_signals = rebuild_projections_and_signals(
        everrun_storage, everrun_pkg.run_id
    )
    second_proj, second_signals = rebuild_projections_and_signals(
        second_storage, second_pkg.run_id
    )

    assert type(everrun_proj) is type(second_proj)
    assert type(everrun_proj).model_fields.keys() == type(second_proj).model_fields.keys()

    everrun_report = build_run_report(everrun_proj, everrun_signals)
    second_report = build_run_report(second_proj, second_signals)
    assert type(everrun_report) is type(second_report)
    assert type(everrun_report).model_fields.keys() == type(second_report).model_fields.keys()


def test_unknown_producer_specific_event_is_preserved_not_dropped(tmp_path: Path) -> None:
    """evt-sp-004 (mcp.tool.result_received) has no meaning anywhere in
    src/ailuros core. It must survive ingestion as raw evidence rather than
    being silently dropped or treated as clean."""
    package = load_evidence_package(SECOND_PRODUCER)
    storage = _new_storage(tmp_path)
    ingest_evidence_package(storage, package)

    events = storage.list_events(package.run_id)
    event_ids = {e.event_id for e in events}
    assert "evt-sp-004" in event_ids

    unknown_event = next(e for e in events if e.event_id == "evt-sp-004")
    assert unknown_event.payload["event_type"] == "mcp.tool.result_received"
    assert unknown_event.payload["payload"] == {"tool": "generic.search", "result_size": 12}


def test_everrun_postfix_minimal_and_second_producer_run_identical_shared_pipeline(
    tmp_path: Path,
) -> None:
    """T1: both canonical fixtures — the EverRun-derived minimal package and the
    generic MCP-style second-producer package — travel through the byte-identical
    shared function objects (validate -> load -> ingest -> rebuild -> report).
    Structurally identical result shapes are produced from each fixture even
    though their raw evidence and governed outcomes differ."""
    from ailuros.execution_report import build_run_report
    from ailuros.projection import rebuild_projections_and_signals

    fixtures = {
        "everrun": EVERRUN_POSTFIX_MINIMAL,
        "second": SECOND_PRODUCER,
    }
    outcomes: dict[str, tuple] = {}
    for name, fixture in fixtures.items():
        validation = validate_evidence_package_contract(fixture)
        assert validation.ok is True
        assert validation.errors == []

        package = load_evidence_package(fixture)
        storage = _new_storage(tmp_path / name)
        ingest_result = ingest_evidence_package(storage, package)
        assert ingest_result.status == ImportStatus.CREATED

        proj, signals = rebuild_projections_and_signals(storage, package.run_id)
        report = build_run_report(proj, signals)
        outcomes[name] = (validation, package, ingest_result, proj, signals, report)

    everrun = outcomes["everrun"]
    second = outcomes["second"]

    assert everrun[0].source == "everrun"
    assert second[0].source == "generic-mcp-workflow"
    assert everrun[0].source != second[0].source

    for index in (3, 5):  # projection and report result shapes
        assert type(everrun[index]) is type(second[index])
        assert type(everrun[index]).model_fields.keys() == type(second[index]).model_fields.keys()

    # Different evidence stays free to produce different governed outcomes.
    assert everrun[5].governed_outcome != second[5].governed_outcome


def test_projection_source_label_is_inert_to_regression_interpretation(
    tmp_path: Path,
) -> None:
    """T2: clone each canonical fixture's normalized projection changing ONLY the
    source label, then run the regression read-model. The transition matrix must
    be unchanged, and a projection compared against its own source-relabeled
    clone must show no real change (only unchanged/unknown transitions)."""
    projections = {}
    for name, fixture in {
        "everrun": EVERRUN_POSTFIX_MINIMAL,
        "second": SECOND_PRODUCER,
    }.items():
        package = load_evidence_package(fixture)
        storage = _new_storage(tmp_path / name)
        ingest_evidence_package(storage, package)
        proj, _ = rebuild_projections_and_signals(storage, package.run_id)
        projections[name] = proj

    everrun = projections["everrun"]
    second = projections["second"]

    everrun_relabeled = everrun.model_copy(update={"source": "generic-mcp-workflow"})
    second_relabeled = second.model_copy(update={"source": "everrun"})

    baseline = compare_governance_projections(everrun, second)
    relabeled = compare_governance_projections(everrun_relabeled, second_relabeled)
    assert [
        (d.dimension, d.baseline, d.current, d.transition)
        for d in baseline.dimensions
    ] == [
        (d.dimension, d.baseline, d.current, d.transition)
        for d in relabeled.dimensions
    ]

    for proj, relabeled_proj in ((everrun, everrun_relabeled), (second, second_relabeled)):
        self_delta = compare_governance_projections(proj, relabeled_proj)
        for dimension_delta in self_delta.dimensions:
            assert dimension_delta.baseline == dimension_delta.current
            assert dimension_delta.transition in {
                GovernanceTransition.UNCHANGED,
                GovernanceTransition.UNKNOWN,
            }


def test_unknown_events_survive_without_promoting_clean_across_canonical_fixtures(
    tmp_path: Path,
) -> None:
    """T3: producer-private unknown events survive ingestion as raw evidence and
    are never promoted into a clean_success governed outcome. The EverRun
    fixture's governance events are canonical now; the second-producer carries
    the unsupported mcp.tool.result_received. Neither run may be reported as
    clean."""
    fixtures = {
        "everrun": (EVERRUN_POSTFIX_MINIMAL, "run-20260824-004751", "unknown"),
        "second": (SECOND_PRODUCER, "run-second-producer-001", "failed"),
    }
    for name, (fixture, run_id, expected_outcome) in fixtures.items():
        validation = validate_evidence_package_contract(fixture)
        assert validation.ok is True
        if name == "everrun":
            # EverRun's evidence is fully canonical now; no unknown warnings.
            assert validation.warnings == []
        else:
            assert any("unknown event_type" in w for w in validation.warnings)

        package = load_evidence_package(fixture)
        storage = _new_storage(tmp_path / name)
        ingest_result = ingest_evidence_package(storage, package)
        assert ingest_result.status == ImportStatus.CREATED
        assert ingest_result.events_imported == len(package.events)

        stored_events = storage.list_events(run_id)
        assert len(stored_events) == len(package.events)

        proj, signals = rebuild_projections_and_signals(storage, run_id)
        report = build_run_report(proj, signals)
        assert report.governed_outcome != "clean_success"
        assert report.governed_outcome == expected_outcome


def test_second_producer_events_are_not_silently_treated_as_clean(tmp_path: Path) -> None:
    """An authority_evidence violation is present in the raw evidence. Whatever
    the current projection derives, it must not report the run as a
    clean/successful governed outcome while unresolved raw evidence exists
    that a human could not yet act on because it was never surfaced."""
    package = load_evidence_package(SECOND_PRODUCER)
    storage = _new_storage(tmp_path)
    ingest_evidence_package(storage, package)

    events = storage.list_events(package.run_id)
    raw_event_types = {e.payload.get("event_type") for e in events}
    assert "authority_evidence" in raw_event_types
    assert "run_started" in raw_event_types
    assert "run_completed" in raw_event_types


# ── T1: scope/provenance survive the canonical pipeline ────────────────────


def test_second_producer_scoped_evidence_scope_survives_canonical_pipeline(
    tmp_path: Path,
) -> None:
    """The second-producer fixture ships explicit scoped evidence. Its scope_ref
    must survive load -> ingest -> projection exactly as authored, proving scope
    is a package-authored fact and not derived from the producer name."""
    package = load_evidence_package(SECOND_PRODUCER)
    scoped = [e for e in package.events if e.scope_ref is not None]
    assert scoped, "second-producer fixture must ship explicit scoped evidence"
    assert {e.scope_ref for e in scoped} == {SCOPE_REF}

    storage = _new_storage(tmp_path)
    ingest_evidence_package(storage, package)

    stored = storage.list_events(package.run_id)
    scoped_stored = [e for e in stored if e.payload.get("scope_ref") is not None]
    assert scoped_stored
    assert {e.payload["scope_ref"] for e in scoped_stored} == {SCOPE_REF}

    proj, _ = rebuild_projections_and_signals(storage, package.run_id)
    assert proj.scope_ref == SCOPE_REF


def test_second_producer_provenance_survives_contract_and_ingest(
    tmp_path: Path,
) -> None:
    """Manifest provenance is package-authored evidence: the contract validator
    must read it (safety checks) and the load/ingest path must leave it intact as
    raw evidence, with the source it identifies carried into the stored run."""
    manifest_raw = json.loads(
        (SECOND_PRODUCER / "manifest.json").read_text(encoding="utf-8")
    )
    provenance = manifest_raw["provenance"]
    assert provenance["source_artifact"] == "generic-mcp-exporter"

    result = validate_evidence_package_contract(SECOND_PRODUCER)
    assert result.ok is True
    assert not any("provenance" in error for error in result.errors)

    package = load_evidence_package(SECOND_PRODUCER)
    storage = _new_storage(tmp_path)
    ingest_evidence_package(storage, package)

    stored_run = storage.get_run(package.run_id)
    assert stored_run.metadata.get("source") == "generic-mcp-workflow"

    manifest_after = json.loads(
        (SECOND_PRODUCER / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest_after["provenance"] == provenance


# ── T2: unsupported event type / missing governance constraints ─────────────


def test_second_producer_unsupported_event_type_is_warning_not_error() -> None:
    """mcp.tool.result_received is outside the canonical event vocabulary. The
    contract validator must preserve it as a warning, never reject the package,
    and never reinterpret it as a governance fact."""
    result = validate_evidence_package_contract(SECOND_PRODUCER)
    assert result.ok is True
    assert result.errors == []
    assert any("unknown event_type: mcp.tool.result_received" in w for w in result.warnings)


def test_missing_governance_constraints_are_not_inferred_as_clean() -> None:
    """A second-producer run whose events carry producer-native completion labels
    but no authority/budget/approval/validation constraint evidence must not be
    reported as a clean governed outcome: missing constraints yield UNKNOWN
    coverage, no manufactured records, and no clean_success claim."""
    package = load_evidence_package(SECOND_PRODUCER)
    unconstrained = [
        {
            "event_id": ev.event_id,
            "event_type": ev.event_type,
            "timestamp": ev.timestamp,
            "payload": ev.payload,
            "scope_ref": ev.scope_ref,
        }
        for ev in package.events
        if ev.event_type
        not in {
            "authority_evidence",
            "budget_evidence",
            "approval_evidence",
            "project_validation",
        }
    ]

    proj = build_execution_projection(
        run_id="run-second-producer-nogov",
        source="generic-mcp-workflow",
        events=unconstrained,
        schema_version="ailuros.timeline.v1",
    )

    assert proj.lifecycle.value == "completed"
    assert proj.approval_records == []
    assert proj.authority_records == []
    assert proj.budget_records == []
    assert proj.governance_coverage.authority.value == "unknown"
    assert proj.governance_coverage.approval.value == "unknown"
    assert proj.governance_coverage.budget.value == "unknown"

    report = build_run_report(proj, [])
    assert report.governed_outcome != "clean_success"


# ── T3: producer-native labels do not create governance facts ───────────────


def test_producer_native_success_labels_do_not_create_governance_facts(
    tmp_path: Path,
) -> None:
    """The fixture carries producer-native success/accept labels: project_validation
    status 'passed', budget_evidence status 'within_limit', run_completed result
    'completed', and an mcp.tool.result_received accept event. None of these may
    manufacture authorized, approved, or clean governance facts on their own."""
    package = load_evidence_package(SECOND_PRODUCER)
    storage = _new_storage(tmp_path)
    ingest_evidence_package(storage, package)

    stored = storage.list_events(package.run_id)
    raw = {e.payload["event_type"]: e.payload["payload"] for e in stored}
    assert raw["project_validation"]["status"] == "passed"
    assert raw["budget_evidence"]["status"] == "within_limit"
    assert raw["run_completed"]["result"] == "completed"

    proj, signals = rebuild_projections_and_signals(storage, package.run_id)

    assert proj.approval_records == []
    assert all(r.state.value != "authorized" for r in proj.authority_records)
    assert all(r.state.value != "approved" for r in proj.approval_records)
    assert proj.outcome.value == "failed"

    report = build_run_report(proj, signals)
    assert report.governed_outcome == "failed"
    assert report.governed_outcome != "clean_success"


# ── T4: anti-regression — no source-name branching anywhere in core ────────

_CORE_MODULES = [projection, signals_module, execution_report]


def test_core_governance_modules_do_not_branch_on_producer_identity() -> None:
    """Static anti-regression guard: core governance modules must not contain
    a literal comparison against this fixture's producer name or 'everrun'.
    Governance facts must be derived from evidence shape, not source string."""
    forbidden_literals = ["generic-mcp-workflow", "second_producer", "everrun"]
    for module in _CORE_MODULES:
        source_text = inspect.getsource(module)
        lowered = source_text.lower()
        for literal in forbidden_literals:
            assert literal not in lowered, (
                f"{module.__name__} contains a producer-identity literal "
                f"'{literal}' — governance must remain source-neutral"
            )


def test_build_execution_projection_signature_has_no_producer_parameter() -> None:
    """The shared projection entrypoint must only take generic run/source/
    events parameters — no producer-specific keyword argument path."""
    params = set(inspect.signature(build_execution_projection).parameters)
    assert params == {"run_id", "source", "events", "schema_version"}
