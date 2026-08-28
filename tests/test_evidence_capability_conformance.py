"""Capability-level governance evidence conformance tests.

Locks the capability matrix, the deterministic evaluator, source neutrality and
the no-fabrication behavior: missing optional governance evidence yields
missing/partial semantics, never fabricated success, and capability rules read
only canonical event types and structured payload fields.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from ailuros.cli import app
from ailuros.evidence_conformance import (
    CapabilityStatus,
    EvidenceConformanceResult,
    capability_ids,
    conformance_result_to_json,
    conformance_result_to_markdown,
    evaluate_capability,
    evaluate_evidence_conformance,
)

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
SECOND_PRODUCER = REPO_ROOT / "fixtures" / "runtime-evidence" / "second-producer"
EVERRUN_POSTFIX_MINIMAL = (
    REPO_ROOT / "fixtures" / "runtime-evidence" / "everrun-postfix-minimal"
)

EXPECTED_CAPABILITIES = (
    "lifecycle",
    "outcome",
    "regression_prerequisites",
    "authority",
    "approval",
    "budget",
    "scope",
    "validation",
)

ALL_EVALUABLE = {cap: "evaluable" for cap in EXPECTED_CAPABILITIES}


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _make_manifest(run_id: str, source: str = "unit-producer") -> dict:
    return {
        "package_version": "1",
        "source": source,
        "governance_mode": "observe",
        "schema_version": "ailuros.timeline.v1",
        "run_id": run_id,
        "generated_at": "2026-08-25T00:00:00+00:00",
        "files": [
            {"name": "manifest.json", "required": True},
            {"name": "timeline.json", "required": True},
        ],
    }


def _event(
    event_id: str,
    event_type: str,
    payload: dict,
    scope_ref: str | None = None,
) -> dict:
    event: dict = {
        "event_id": event_id,
        "event_type": event_type,
        "timestamp": "2026-08-25T00:00:00+00:00",
        "payload": payload,
    }
    if scope_ref is not None:
        event["scope_ref"] = scope_ref
    return event


def _make_package(
    tmp_path: Path,
    *,
    run_id: str = "run-conformance-001",
    source: str = "unit-producer",
    include_terminal: bool = True,
    include_authority: bool = True,
    include_approval: bool = True,
    include_budget: bool = True,
    include_scope: bool = True,
    include_validation: bool = True,
) -> Path:
    events: list[dict] = [
        _event("evt-001", "run_started", {"workflow": "unit"})
    ]
    if include_terminal:
        events.append(_event("evt-002", "run_completed", {"result": "completed"}))
    if include_authority:
        events.append(
            _event(
                "evt-003",
                "authority_evidence",
                {
                    "actor": "unit-agent",
                    "action": "invoke",
                    "status": "authorized",
                    "required": True,
                },
            )
        )
    if include_approval:
        events.append(
            _event(
                "evt-004",
                "approval_evidence",
                {
                    "subject": "unit-action",
                    "decision": "approved",
                    "required": True,
                },
            )
        )
    if include_budget:
        events.append(
            _event(
                "evt-005",
                "budget_evidence",
                {
                    "subject": "unit-budget",
                    "unit": "calls",
                    "limit": 100,
                    "consumed": 5,
                    "required": True,
                },
            )
        )
    if include_scope:
        events.append(_event("evt-006", "project_scope", {"status": "clean"}))
    if include_validation:
        events.append(
            _event("evt-007", "project_validation", {"status": "passed"})
        )

    pkg = tmp_path / "pkg"
    pkg.mkdir(parents=True, exist_ok=True)
    _write_json(pkg / "manifest.json", _make_manifest(run_id, source))
    _write_json(
        pkg / "timeline.json",
        {
            "schema_version": "ailuros.timeline.v1",
            "run_id": run_id,
            "events": events,
        },
    )
    return pkg


def _statuses(result: EvidenceConformanceResult) -> dict[str, str]:
    return {item.capability: item.status.value for item in result.capabilities}


def _missing(result: EvidenceConformanceResult) -> dict[str, list[str]]:
    return {
        item.capability: list(item.missing_evidence)
        for item in result.capabilities
    }


# ── T1: minimum capability matrix and closed status vocabulary ─────────────


def test_standard_capability_matrix_is_exactly_the_declared_set() -> None:
    assert capability_ids() == EXPECTED_CAPABILITIES


def test_status_vocabulary_is_closed_and_documented() -> None:
    assert {status.value for status in CapabilityStatus} == {
        "evaluable",
        "missing_evidence",
        "unsupported",
    }


def test_unknown_capability_is_unsupported_not_evaluable() -> None:
    result = evaluate_capability([], "not_a_canonical_capability")
    assert result.status == CapabilityStatus.UNSUPPORTED
    assert result.missing_evidence == []


# ── T2: deterministic evaluator over canonical structured events ───────────


def test_full_evidence_package_is_evaluable_for_every_capability(
    tmp_path: Path,
) -> None:
    result = evaluate_evidence_conformance(_make_package(tmp_path))
    assert result.package_valid is True
    assert _statuses(result) == ALL_EVALUABLE
    assert all(item.missing_evidence == [] for item in result.capabilities)


def test_minimal_run_anchor_is_partial_never_fabricated(tmp_path: Path) -> None:
    """Only run_started: lifecycle is evaluable but outcome and regression
    prerequisites are missing evidence — never fabricated success."""
    pkg = _make_package(
        tmp_path,
        include_terminal=False,
        include_authority=False,
        include_approval=False,
        include_budget=False,
        include_scope=False,
        include_validation=False,
    )
    result = evaluate_evidence_conformance(pkg)
    assert result.package_valid is True
    statuses = _statuses(result)
    assert statuses["lifecycle"] == "evaluable"
    assert statuses["outcome"] == "missing_evidence"
    assert statuses["regression_prerequisites"] == "missing_evidence"
    assert _missing(result)["regression_prerequisites"] == [
        "run_completed",
        "run_failed",
    ]
    for cap in (
        "authority",
        "approval",
        "budget",
        "scope",
        "validation",
    ):
        assert statuses[cap] == "missing_evidence"


# ── T2/T3: regression prerequisites requires a canonical terminal side ─────


def test_regression_prerequisites_is_satisfied_by_run_completed_alone() -> None:
    """A canonical run_completed alone is sufficient for regression
    prerequisites: ordered comparison needs a terminal side."""
    events = [_event("evt-001", "run_completed", {"result": "completed"})]
    result = evaluate_capability(events, "regression_prerequisites")
    assert result.status == CapabilityStatus.EVALUABLE
    assert result.missing_evidence == []


def test_regression_prerequisites_is_satisfied_by_run_failed_alone() -> None:
    """A canonical run_failed alone is also sufficient: either terminal event
    independently satisfies regression prerequisites."""
    events = [_event("evt-001", "run_failed", {"error": "boom"})]
    result = evaluate_capability(events, "regression_prerequisites")
    assert result.status == CapabilityStatus.EVALUABLE
    assert result.missing_evidence == []


def test_regression_prerequisites_is_never_satisfied_by_run_started_alone() -> None:
    """Mutation guard: run_started alone must never satisfy regression
    prerequisites, and the missing ids stay the precise terminal identifiers.
    Exercises the behavioral evaluator (evaluate_capability), not source text."""
    events = [_event("evt-001", "run_started", {"workflow": "unit"})]
    result = evaluate_capability(events, "regression_prerequisites")
    assert result.status == CapabilityStatus.MISSING_EVIDENCE
    assert result.missing_evidence == ["run_completed", "run_failed"]


def test_second_producer_fixture_capability_statuses() -> None:
    result = evaluate_evidence_conformance(SECOND_PRODUCER)
    assert result.package_valid is True
    statuses = _statuses(result)
    assert statuses["lifecycle"] == "evaluable"
    assert statuses["outcome"] == "evaluable"
    assert statuses["regression_prerequisites"] == "evaluable"
    assert statuses["authority"] == "evaluable"
    assert statuses["budget"] == "evaluable"
    assert statuses["validation"] == "evaluable"
    assert statuses["approval"] == "missing_evidence"
    assert statuses["scope"] == "missing_evidence"


def test_everrun_postfix_minimal_fixture_capability_statuses() -> None:
    result = evaluate_evidence_conformance(EVERRUN_POSTFIX_MINIMAL)
    assert result.package_valid is True
    statuses = _statuses(result)
    assert statuses["lifecycle"] == "evaluable"
    assert statuses["regression_prerequisites"] == "missing_evidence"
    assert statuses["scope"] == "evaluable"
    assert statuses["validation"] == "evaluable"
    assert statuses["outcome"] == "missing_evidence"
    assert statuses["authority"] == "missing_evidence"
    assert statuses["approval"] == "missing_evidence"
    assert statuses["budget"] == "missing_evidence"


def test_missing_evidence_is_precise_identifier_not_prose() -> None:
    """T2: precise missing evidence identifiers rather than prose-only reasons."""
    result = evaluate_evidence_conformance(SECOND_PRODUCER)
    assert _missing(result)["approval"] == ["approval_evidence.payload.subject"]
    assert _missing(result)["scope"] == ["project_scope"]


def test_budget_requires_both_subject_and_unit_structured_fields(
    tmp_path: Path,
) -> None:
    """A budget_evidence event is not enough: projection needs subject AND unit
    to build a BudgetRecord, so a missing unit is reported as missing evidence."""
    pkg = _make_package(
        tmp_path,
        include_terminal=False,
        include_authority=False,
        include_approval=False,
        include_scope=False,
        include_validation=False,
        include_budget=True,
    )
    timeline = json.loads((pkg / "timeline.json").read_text(encoding="utf-8"))
    timeline["events"] = [
        e for e in timeline["events"] if e["event_type"] != "budget_evidence"
    ]
    timeline["events"].append(
        _event("evt-005", "budget_evidence", {"subject": "unit-budget"})
    )
    _write_json(pkg / "timeline.json", timeline)

    result = evaluate_evidence_conformance(pkg)
    statuses = _statuses(result)
    assert statuses["budget"] == "missing_evidence"
    assert _missing(result)["budget"] == ["budget_evidence.payload.unit"]


def test_authority_requires_non_empty_actor_structured_field(
    tmp_path: Path,
) -> None:
    """An authority_evidence event with an empty actor builds no record; the
    capability must report the structured payload field as missing."""
    pkg = _make_package(
        tmp_path,
        include_terminal=False,
        include_approval=False,
        include_budget=False,
        include_scope=False,
        include_validation=False,
    )
    timeline = json.loads((pkg / "timeline.json").read_text(encoding="utf-8"))
    timeline["events"] = [
        e for e in timeline["events"] if e["event_type"] != "authority_evidence"
    ]
    timeline["events"].append(
        _event("evt-003", "authority_evidence", {"actor": "", "status": "authorized"})
    )
    _write_json(pkg / "timeline.json", timeline)

    result = evaluate_evidence_conformance(pkg)
    assert _statuses(result)["authority"] == "missing_evidence"
    assert _missing(result)["authority"] == ["authority_evidence.payload.actor"]


# ── T4: source neutrality and independent degradation ──────────────────────


def test_relabel_to_unseen_producer_is_inert(tmp_path: Path) -> None:
    """Relabel source/agent/framework metadata to an arbitrary unseen producer
    and prove the conformance result is identical (source never enters the
    decision logic)."""
    relabeled = tmp_path / "relabeled"
    shutil.copytree(SECOND_PRODUCER, relabeled)

    unseen = "zzz-unseen-producer-xyzzy"
    manifest = json.loads((relabeled / "manifest.json").read_text(encoding="utf-8"))
    manifest["source"] = unseen
    manifest["metadata"]["agent_name"] = unseen
    manifest["provenance"]["metadata"]["framework"] = unseen
    _write_json(relabeled / "manifest.json", manifest)

    timeline = json.loads((relabeled / "timeline.json").read_text(encoding="utf-8"))
    for event in timeline["events"]:
        event["metadata"] = {"producer": unseen}
    _write_json(relabeled / "timeline.json", timeline)

    baseline = evaluate_evidence_conformance(SECOND_PRODUCER)
    relabeled_result = evaluate_evidence_conformance(relabeled)

    assert relabeled_result.source == unseen
    assert relabeled_result.source != baseline.source
    assert _statuses(relabeled_result) == _statuses(baseline)
    assert _missing(relabeled_result) == _missing(baseline)
    assert relabeled_result.package_valid == baseline.package_valid


def test_removing_terminal_evidence_degrades_outcome_and_regression_prerequisites(
    tmp_path: Path,
) -> None:
    full = _make_package(tmp_path)
    full_statuses = _statuses(evaluate_evidence_conformance(full))
    assert full_statuses == ALL_EVALUABLE

    degraded = _make_package(tmp_path / "degraded", include_terminal=False)
    statuses = _statuses(evaluate_evidence_conformance(degraded))
    expected = dict(ALL_EVALUABLE)
    expected["outcome"] = "missing_evidence"
    expected["regression_prerequisites"] = "missing_evidence"
    assert statuses == expected


def test_removing_authority_evidence_degrades_only_authority(
    tmp_path: Path,
) -> None:
    degraded = _make_package(tmp_path, include_authority=False)
    statuses = _statuses(evaluate_evidence_conformance(degraded))
    expected = dict(ALL_EVALUABLE)
    expected["authority"] = "missing_evidence"
    assert statuses == expected


def test_removing_approval_evidence_degrades_only_approval(tmp_path: Path) -> None:
    degraded = _make_package(tmp_path, include_approval=False)
    statuses = _statuses(evaluate_evidence_conformance(degraded))
    expected = dict(ALL_EVALUABLE)
    expected["approval"] = "missing_evidence"
    assert statuses == expected


def test_removing_budget_evidence_degrades_only_budget(tmp_path: Path) -> None:
    degraded = _make_package(tmp_path, include_budget=False)
    statuses = _statuses(evaluate_evidence_conformance(degraded))
    expected = dict(ALL_EVALUABLE)
    expected["budget"] = "missing_evidence"
    assert statuses == expected


# ── Determinism and rendering ──────────────────────────────────────────────


def test_json_output_is_deterministic(tmp_path: Path) -> None:
    result = evaluate_evidence_conformance(SECOND_PRODUCER)
    first = conformance_result_to_json(result)
    second = conformance_result_to_json(result)
    assert first == second
    assert json.loads(first)["capabilities"][0]["capability"] == "lifecycle"


def test_markdown_identifies_capability_status_and_missing_evidence(
    tmp_path: Path,
) -> None:
    rendered = conformance_result_to_markdown(
        evaluate_evidence_conformance(SECOND_PRODUCER)
    )
    assert "# Evidence Capability Conformance" in rendered
    assert "| Capability | Status | Missing evidence |" in rendered
    assert "| approval | missing_evidence | approval_evidence.payload.subject |" in rendered


def test_structurally_invalid_package_is_not_fabricated_evaluable(
    tmp_path: Path,
) -> None:
    """Structural invalidity is reported separately and never manufactures
    capability success: a missing timeline means every capability is missing
    evidence while package_valid is False."""
    pkg = _make_package(tmp_path)
    (pkg / "timeline.json").unlink()

    result = evaluate_evidence_conformance(pkg)
    assert result.package_valid is False
    assert set(_statuses(result).values()) == {"missing_evidence"}


# ── T3: CLI surface ────────────────────────────────────────────────────────


def test_cli_json_identifies_capability_status_and_missing_evidence() -> None:
    result = CliRunner().invoke(
        app, ["evidence-conformance", str(SECOND_PRODUCER)]
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["package_valid"] is True
    by_name = {c["capability"]: c for c in data["capabilities"]}
    assert by_name["authority"]["status"] == "evaluable"
    assert by_name["approval"]["status"] == "missing_evidence"
    assert by_name["approval"]["missing_evidence"] == [
        "approval_evidence.payload.subject"
    ]


def test_cli_partial_conformance_is_not_nonzero_exit(tmp_path: Path) -> None:
    """A structurally valid package with missing evidence must still exit zero:
    partial conformance is not a structural failure."""
    pkg = _make_package(
        tmp_path,
        include_approval=False,
        include_budget=False,
        include_scope=False,
    )
    result = CliRunner().invoke(app, ["evidence-conformance", str(pkg)])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["package_valid"] is True
    assert any(
        c["status"] == "missing_evidence" for c in data["capabilities"]
    )


def test_cli_markdown_output() -> None:
    result = CliRunner().invoke(
        app, ["evidence-conformance", str(SECOND_PRODUCER), "--format", "md"]
    )
    assert result.exit_code == 0
    assert "| approval | missing_evidence |" in result.stdout


def _wrap(event: dict) -> dict:
    """Represent a canonical event as an ``external_evidence`` wrapper."""
    wrapper = {
        "event_type": event["event_type"],
        "payload": event.get("payload", {}),
        "metadata": event.get("metadata", {}),
    }
    if event.get("scope_ref"):
        wrapper["scope_ref"] = event["scope_ref"]
    return {
        "event_id": event.get("event_id", ""),
        "event_type": "external_evidence",
        "timestamp": event.get("timestamp", "2026-08-25T00:00:00+00:00"),
        "payload": wrapper,
    }


def _make_wrapped_package(
    tmp_path: Path,
    *,
    run_id: str = "run-wrapped-001",
    source: str = "unit-producer",
) -> Path:
    """Build a valid package with its canonical events stored as wrappers."""
    unwrapped_pkg = _make_package(tmp_path / "unwrapped", run_id=run_id, source=source)
    raw_timeline = json.loads(
        (unwrapped_pkg / "timeline.json").read_text(encoding="utf-8")
    )
    raw_timeline["events"] = [_wrap(event) for event in raw_timeline["events"]]
    package_dir = tmp_path / "wrapped"
    package_dir.mkdir(parents=True, exist_ok=True)
    _write_json(package_dir / "manifest.json", _make_manifest(run_id, source))
    _write_json(package_dir / "timeline.json", raw_timeline)
    return package_dir


def test_wrapped_and_unwrapped_packages_agree_on_evaluability(tmp_path: Path) -> None:
    unwrapped = _make_package(tmp_path / "unwrapped")
    wrapped = _make_wrapped_package(tmp_path / "wrapped")

    unwrapped_statuses = _statuses(evaluate_evidence_conformance(unwrapped))
    wrapped_statuses = _statuses(evaluate_evidence_conformance(wrapped))

    assert unwrapped_statuses == ALL_EVALUABLE
    assert wrapped_statuses == unwrapped_statuses
    for capability in ("authority", "approval", "budget"):
        assert wrapped_statuses[capability] == "evaluable"


def test_malformed_external_wrapper_produces_no_synthetic_evidence() -> None:
    malformed = [
        {
            "event_id": "evt-malformed",
            "event_type": "external_evidence",
            "timestamp": "2026-08-25T00:00:00+00:00",
            "payload": {"event_type": "authority_evidence", "payload": []},
        },
        {
            "event_id": "evt-missing-type",
            "event_type": "external_evidence",
            "timestamp": "2026-08-25T00:00:00+00:00",
            "payload": {"payload": {}},
        },
    ]

    for capability in ("authority", "approval", "budget"):
        result = evaluate_capability(malformed, capability)
        assert result.status == CapabilityStatus.MISSING_EVIDENCE
        assert result.missing_evidence
