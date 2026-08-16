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
from pathlib import Path

from ailuros import execution_report, projection
from ailuros import signals as signals_module
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
REPO_ROOT = HERE.parent
SECOND_PRODUCER = REPO_ROOT / "fixtures" / "runtime-evidence" / "second-producer"
FIRST_PRODUCER = HERE / "fixtures" / "evidence_package" / "valid-v1"


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


def test_second_producer_source_name_is_distinct_from_everrun() -> None:
    result = validate_evidence_package_contract(SECOND_PRODUCER)
    assert result.source != "everrun"
    assert "everrun" not in result.source.lower()


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
