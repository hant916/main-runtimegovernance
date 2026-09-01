"""Canonical producer compatibility matrix (8080).

Bounded regression matrix over every currently evidence-backed canonical
producer fixture. A producer is "evidence-backed" only when it is already
justified by production dogfood (`fixtures/runtime-evidence/everrun-postfix-minimal`,
accepted by packs 8065/8066 and replayed by 8076/8077) or by an existing
conformance test (`fixtures/runtime-evidence/second-producer`, exercised by
`tests/test_second_producer_conformance.py`).

T1 — Inventory. The matrix registers exactly two producers: `everrun` and the
generic MCP-style `second-producer`. The synthetic contract samples under
`tests/fixtures/evidence_package/*` (`sample-agent-v1`, `sample-agent-v0`) are
NOT producers: they back generic adapter/contract tests, not a framework or
producer claim, so they are excluded from the matrix (red line: do not claim
unsupported producers are proven).

T2 — Expected canonical facts. For each fixture the matrix records audit
acceptance (contract `ok`, decision, rules evaluated, unknown-event registry
warnings) and a minimal evidence-backed set of projection/report facts
(lifecycle, native outcome, validation, scope, scope_ref, governed outcome,
why-stopped, decision/event counts, governance coverage, authority/approval/
budget records, signal set, and evidence attribution refs).

T3 — Shared-path matrix. Every producer runs through the byte-identical shared
pipeline (validate -> audit -> load -> ingest -> rebuild -> report -> governed
result). The tests are parameterized by fixture, not branched by producer, and
the shared callables are asserted by signature/source so no producer-specific
fork can creep in.

T4 — Proven boundary. The proven set is exactly the two producers above. Every
other named framework (LangGraph, OpenAI Agents SDK, an MCP server, etc.)
remains unproven and is asserted to be absent from the matrix.

Red lines honored:
- No unsupported framework is claimed proven.
- No fixture is modified to force identical outcomes; the two producers
  legitimately project different governed outcomes (unknown vs failed).
"""

from __future__ import annotations

import inspect
import json
import shutil
from pathlib import Path

import pytest

from ailuros.adapters.evidence_package import (
    ImportStatus,
    audit_evidence_package,
    ingest_evidence_package,
    load_evidence_package,
    validate_evidence_package_contract,
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
SECOND_PRODUCER_FIXTURE = (
    REPO_ROOT / "fixtures" / "runtime-evidence" / "second-producer"
)

# T1: evidence-backed canonical producer fixtures and their expected canonical
# facts (audit acceptance + minimal evidence-backed projection/report facts).
PRODUCERS: dict[str, dict] = {
    "everrun": {
        "path": EVERRUN_FIXTURE,
        "source": "everrun",
        "run_id": "run-20260824-004751",
        "schema_version": "ailuros.timeline.v1",
        "events": 5,
        "unknown_event_warnings": 3,
        "expected": {
            "lifecycle": "running",
            "outcome": "unknown",
            "validation": "passed",
            "scope": "clean",
            "scope_ref": None,
            "governed_outcome": "unknown",
            "aggregate_governed_outcome": "unknown",
            "why_stopped": "execution_control: human_review",
            "decision_count": 1,
            "event_count": 5,
            "coverage": {
                "authority": "unknown",
                "approval": "unknown",
                "budget": "unknown",
                "validation": "evaluated",
                "scope": "evaluated",
            },
            "authority_records": [],
            "approval_records": [],
            "budget_records": [],
            "signal_types": [
                "missing_run_terminal_evidence",
                "temporal_integrity",
            ],
            "evidence_refs": [
                "096c61058c4836c11123ae65c44d46e8f95bd79290d33a1d522f1ca7c4d4b97c",
                "26bd6b9f28326958c886af9abc2a9bb59ef2c4ff72ac55a5687fd7059e8f8707",
                "4c28b5dff4c2ad8ffa482221f5ccb5bab0ab583d46be7400ec90051dcad5d2fe",
                "d125830d3781ae3a9a1a5db6ecd6834b679a120694a05a79bbd05f541474fa99",
                "e0226f129d79a3277853613435f43b95cee6f8a0f2253d16fb321be6e63ef7ef",
            ],
        },
    },
    "second-producer": {
        "path": SECOND_PRODUCER_FIXTURE,
        "source": "generic-mcp-workflow",
        "run_id": "run-second-producer-001",
        "schema_version": "ailuros.timeline.v1",
        "events": 6,
        "unknown_event_warnings": 4,
        "expected": {
            "lifecycle": "completed",
            "outcome": "failed",
            "validation": "passed",
            "scope": "unknown",
            "scope_ref": "scope-mcp-sp-001",
            "governed_outcome": "failed",
            "aggregate_governed_outcome": "failed",
            "why_stopped": "lifecycle: completed (signals: authority_violation)",
            "decision_count": 0,
            "event_count": 6,
            "coverage": {
                "authority": "evaluated",
                "approval": "unknown",
                "budget": "evaluated",
                "validation": "evaluated",
                "scope": "unknown",
            },
            "authority_records": [
                ("violation", "generic-mcp-agent", ["evt-sp-002"])
            ],
            "approval_records": [],
            "budget_records": ["within_limit"],
            "signal_types": ["authority_violation"],
            "evidence_refs": [
                "evt-sp-001",
                "evt-sp-002",
                "evt-sp-003",
                "evt-sp-005",
                "evt-sp-006",
            ],
        },
    },
}

# T4: named frameworks that are NOT yet evidence-backed and therefore not part
# of the proven matrix. A real external integration emitting this contract
# remains deferred; these names must never appear as proven producers.
UNPROVEN_PRODUCER_NAMES = {
    "langgraph",
    "openai-agents-sdk",
    "mcp-server",
    "claude-code",
    "custom-exporter",
}

PROVEN_PRODUCER_NAMES = set(PRODUCERS)

# A producer label that appears nowhere in the codebase, used to prove that the
# source string is inert for governance facts.
_NEUTRAL_LABEL = "zzz-neutral-relabel-probe"


def _new_storage(tmp_path: Path, name: str) -> SQLiteStorage:
    storage = SQLiteStorage(tmp_path / f"{name}.db")
    storage.init()
    return storage


def _run_shared_pipeline(tmp_path: Path, fixture: Path) -> dict:
    """Run the byte-identical production pipeline, parameterized by fixture.

    The same function objects are used for every producer: contract validation,
    post-run audit, package load, ingest, projection+signal rebuild, governed
    report, and governed execution result. No producer-identity branch exists.
    """
    validation = validate_evidence_package_contract(fixture)
    audit = audit_evidence_package(fixture)
    package = load_evidence_package(fixture)
    storage = _new_storage(tmp_path, package.run_id)
    ingest = ingest_evidence_package(storage, package)
    proj, signals = rebuild_projections_and_signals(storage, package.run_id)
    report = build_run_report(proj, signals)
    result = build_governed_execution_result(proj, signals)
    return {
        "validation": validation,
        "audit": audit,
        "ingest": ingest,
        "proj": proj,
        "signals": signals,
        "report": report,
        "result": result,
        "stored_events": storage.list_events(package.run_id),
    }


def _facts(outcomes: dict) -> dict:
    proj = outcomes["proj"]
    report = outcomes["report"]
    return {
        "lifecycle": proj.lifecycle.value,
        "outcome": proj.outcome.value,
        "validation": proj.validation.value,
        "scope": proj.scope.value,
        "scope_ref": proj.scope_ref,
        "governed_outcome": report.governed_outcome,
        "aggregate_governed_outcome": report.aggregate_governed_outcome,
        "why_stopped": report.why_stopped,
        "decision_count": proj.decision_count,
        "event_count": proj.event_count,
        "coverage": {
            "authority": proj.governance_coverage.authority.value,
            "approval": proj.governance_coverage.approval.value,
            "budget": proj.governance_coverage.budget.value,
            "validation": proj.governance_coverage.validation.value,
            "scope": proj.governance_coverage.scope.value,
        },
        "authority_records": [
            (r.state.value, r.actor, sorted(ref.event_id for ref in r.evidence_refs))
            for r in proj.authority_records
        ],
        "approval_records": [(r.state.value, r.subject) for r in proj.approval_records],
        "budget_records": [r.status for r in proj.budget_records],
        "signal_types": sorted({s.type for s in outcomes["signals"]}),
        "evidence_refs": sorted(ref.event_id for ref in proj.evidence_refs),
    }


# ── T1: inventory is exactly the evidence-backed producers ──────────────────


def test_matrix_inventory_is_exactly_the_evidence_backed_producers() -> None:
    """The matrix registers exactly the two evidence-backed producers, each with
    a real on-disk manifest + timeline. Synthetic contract samples are excluded."""
    assert PROVEN_PRODUCER_NAMES == {"everrun", "second-producer"}
    for meta in PRODUCERS.values():
        assert (meta["path"] / "manifest.json").is_file()
        assert (meta["path"] / "timeline.json").is_file()

    synthetic = [
        p.parent
        for p in (HERE / "fixtures" / "evidence_package").glob("*/manifest.json")
        if p.parent.name.startswith("valid-")
    ]
    assert synthetic, "synthetic contract samples must still exist"
    assert all(p.name not in PROVEN_PRODUCER_NAMES for p in synthetic)


# ── T2: expected audit acceptance and canonical facts per fixture ───────────


@pytest.mark.parametrize("name", sorted(PRODUCERS))
def test_each_producer_audit_acceptance(name: str) -> None:
    meta = PRODUCERS[name]
    validation = validate_evidence_package_contract(meta["path"])

    assert validation.ok is True
    assert validation.errors == []
    assert validation.source == meta["source"]
    assert validation.schema_version == meta["schema_version"]
    assert validation.run_id == meta["run_id"]
    assert validation.events_count == meta["events"]

    unknown = [w for w in validation.warnings if "unknown event_type" in w]
    assert len(unknown) == meta["unknown_event_warnings"]

    audit = audit_evidence_package(meta["path"])
    assert audit.ok is True
    assert audit.decision == "warn"
    assert audit.rules_evaluated == 2
    assert audit.events_count == meta["events"]
    assert audit.run_id == meta["run_id"]


@pytest.mark.parametrize("name", sorted(PRODUCERS))
def test_each_producer_projects_expected_canonical_facts(tmp_path, name: str) -> None:
    meta = PRODUCERS[name]
    outcomes = _run_shared_pipeline(tmp_path, meta["path"])

    assert outcomes["ingest"].status == ImportStatus.CREATED
    assert outcomes["ingest"].events_imported == meta["events"]
    assert outcomes["ingest"].events_skipped == 0

    facts = _facts(outcomes)
    assert facts == meta["expected"]

    # Governed execution result mirrors the report's governed outcome.
    assert outcomes["result"].run_id == meta["run_id"]
    assert (
        outcomes["result"].governed_outcome.value
        == meta["expected"]["governed_outcome"]
    )

    # Every projection evidence ref resolves to a stored raw event.
    stored_ids = {e.event_id for e in outcomes["stored_events"]}
    assert set(facts["evidence_refs"]) <= stored_ids


# ── T3: the matrix is one shared pipeline, parameterized not branched ────────


def test_shared_pipeline_is_parameterized_not_branched() -> None:
    """The shared pipeline takes only (tmp_path, fixture) — no producer
    parameter — so a caller cannot select a producer-specific code path."""
    assert inspect.signature(_run_shared_pipeline).parameters.keys() == {
        "tmp_path",
        "fixture",
    }


@pytest.mark.parametrize("name", sorted(PRODUCERS))
def test_producer_label_is_inert_for_governance_facts(tmp_path, name: str) -> None:
    """Behavioral source-neutrality: relabelling the producer in the manifest
    changes no governance fact.

    This is the load-bearing proof that the pipeline does not branch on
    producer identity. The fixture is copied to a temp dir and its `source`
    (and the provenance framework label) is rewritten to a name that appears
    nowhere in the codebase; every canonical governance fact must be
    byte-identical to the untouched original. The on-disk fixture is never
    modified.
    """
    meta = PRODUCERS[name]
    baseline = _facts(_run_shared_pipeline(tmp_path / "orig", meta["path"]))

    relabelled_dir = tmp_path / "relabelled"
    shutil.copytree(meta["path"], relabelled_dir)
    manifest_path = relabelled_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source"] = _NEUTRAL_LABEL
    manifest["metadata"]["agent_name"] = _NEUTRAL_LABEL
    manifest["provenance"]["metadata"]["framework"] = _NEUTRAL_LABEL
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    relabelled_outcomes = _run_shared_pipeline(tmp_path / "relab", relabelled_dir)

    # The label itself did change — otherwise the test would prove nothing.
    assert relabelled_outcomes["validation"].source == _NEUTRAL_LABEL
    assert relabelled_outcomes["validation"].source != meta["source"]

    # ...but no governance fact moved.
    assert _facts(relabelled_outcomes) == baseline == meta["expected"]

    # The source fixture on disk was not mutated.
    original_manifest = json.loads(
        (meta["path"] / "manifest.json").read_text(encoding="utf-8")
    )
    assert original_manifest["source"] == meta["source"]


@pytest.mark.parametrize("name", sorted(PRODUCERS))
def test_projection_stage_is_neutral_even_when_handed_a_producer_name(
    tmp_path, name: str
) -> None:
    """Directly probe the projection stage with the producer name.

    `rebuild_projections_and_signals` defaults to `source="rebuild"`, so the
    manifest's producer label never reaches `build_execution_projection` on the
    normal path — which means the relabel test above cannot, on its own, prove
    the projection stage is neutral. This test closes that hole by feeding the
    real producer name (and a neutral one) straight into the projection stage
    and asserting the governance facts are identical.
    """
    meta = PRODUCERS[name]
    package = load_evidence_package(meta["path"])
    storage = _new_storage(tmp_path, package.run_id)
    ingest_evidence_package(storage, package)

    def facts_for(source: str) -> tuple:
        proj, signals = rebuild_projections_and_signals(
            storage, package.run_id, source=source
        )
        report = build_run_report(proj, signals)
        return (
            proj.lifecycle,
            proj.outcome,
            proj.validation,
            proj.scope,
            proj.scope_ref,
            proj.decision_count,
            proj.event_count,
            sorted(ref.event_id for ref in proj.evidence_refs),
            report.governed_outcome,
            report.why_stopped,
        )

    assert facts_for(meta["source"]) == facts_for(_NEUTRAL_LABEL)
    assert facts_for(meta["source"]) == facts_for("rebuild")


@pytest.mark.parametrize("name", sorted(PRODUCERS))
def test_each_producer_governed_outcome_is_never_promoted_to_clean(
    tmp_path, name: str
) -> None:
    """Both fixtures carry registry-gap (unknown event_type) warnings. Neither
    may be reported as a clean governed outcome; unknowns/violations stay."""
    meta = PRODUCERS[name]
    outcomes = _run_shared_pipeline(tmp_path, meta["path"])
    assert outcomes["report"].governed_outcome != "clean_success"
    assert outcomes["report"].governed_outcome == meta["expected"]["governed_outcome"]
    assert outcomes["validation"].ok is True
    assert len(outcomes["validation"].warnings) >= meta["unknown_event_warnings"]


def test_all_producers_share_one_pipeline_and_result_shapes(tmp_path) -> None:
    """Both producers traverse the identical pipeline (same shared function
    objects) and produce structurally identical result model shapes, even
    though their raw evidence and governed outcomes differ."""
    outcomes_by_name = {
        name: _run_shared_pipeline(tmp_path, meta["path"])
        for name, meta in PRODUCERS.items()
    }
    projs = [outcomes_by_name[n]["proj"] for n in PRODUCERS]
    reports = [outcomes_by_name[n]["report"] for n in PRODUCERS]

    assert type(projs[0]) is type(projs[1])
    assert type(projs[0]).model_fields.keys() == type(projs[1]).model_fields.keys()
    assert type(reports[0]) is type(reports[1])
    assert type(reports[0]).model_fields.keys() == type(reports[1]).model_fields.keys()

    # Structurally identical, yet genuinely different governance outcomes:
    # the shared shape is not achieved by flattening the producers together.
    governed = {outcomes_by_name[n]["report"].governed_outcome for n in PRODUCERS}
    assert len(governed) > 1, (
        "both producers produced the same governed outcome — the matrix would "
        "not prove that one pipeline handles genuinely different evidence"
    )
    assert {r.run_id for r in projs} == {m["run_id"] for m in PRODUCERS.values()}


# ── T4: the proven boundary is exactly the two producers ────────────────────


def test_proven_boundary_excludes_unproven_frameworks() -> None:
    """No unproven framework may be claimed as a proven producer in the matrix,
    and the documented unproven set is disjoint from the proven set."""
    assert PROVEN_PRODUCER_NAMES == {"everrun", "second-producer"}
    assert PROVEN_PRODUCER_NAMES.isdisjoint(UNPROVEN_PRODUCER_NAMES)
    assert all(name not in PRODUCERS for name in UNPROVEN_PRODUCER_NAMES)
