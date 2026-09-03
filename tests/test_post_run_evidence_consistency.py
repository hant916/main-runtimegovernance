"""Post-run evidence judgment fidelity tests (8096).

Locks the two convergence contracts of the EverRun dogfood repair:

CV1 — semantic recognition consistency. Canonical governance evidence already
supported by capability evaluation (project_scope, structured authority/
approval/budget evidence, governance_context, runtime_role) is not reported as
an unknown event by the structural validator, while genuinely unsupported event
types still produce a warning. Source relabelling never changes recognition.

CV2 — evidence consistency. Already-ingested structured claims that contradict
each other about the same governance fact surface an explicit
``inconsistent_evidence`` state with the exact compared evidence refs/ids and a
deterministic rule id; missing or unsupported evidence is never promoted into a
contradiction.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from ailuros.adapters.evidence_package import (
    audit_evidence_package,
    audit_result_to_dict,
    validate_evidence_package_contract,
)
from ailuros.evidence_conformance import (
    EvidenceInconsistency,
    detect_evidence_inconsistencies,
)
from ailuros.evidence_normalization import canonical_governance_event_types

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
EVERRUN = REPO_ROOT / "fixtures" / "runtime-evidence" / "everrun-postfix-minimal"
SECOND_PRODUCER = REPO_ROOT / "fixtures" / "runtime-evidence" / "second-producer"


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _manifest(run_id: str, source: str = "unit-producer") -> dict:
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


def _event(event_id: str, event_type: str, payload: dict | None = None) -> dict:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "timestamp": "2026-08-25T00:00:00+00:00",
        "payload": payload or {},
    }


def _make_package(tmp_path: Path, events: list[dict], run_id: str = "run-cons") -> Path:
    pkg = tmp_path / "pkg"
    pkg.mkdir(parents=True, exist_ok=True)
    _write_json(pkg / "manifest.json", _manifest(run_id))
    _write_json(
        pkg / "timeline.json",
        {
            "schema_version": "ailuros.timeline.v1",
            "run_id": run_id,
            "events": events,
        },
    )
    return pkg


# ── CV1: semantic recognition consistency ──────────────────────────────────


def test_canonical_governance_boundary_is_shared_and_source_neutral() -> None:
    boundary = canonical_governance_event_types()
    assert "project_scope" in boundary
    assert "project_validation" in boundary
    assert "authority_evidence" in boundary
    assert "approval_evidence" in boundary
    assert "budget_evidence" in boundary
    assert "governance_context" in boundary
    assert "runtime_role" in boundary
    # The boundary is a frozenset of canonical event_type names only.
    assert all(isinstance(name, str) for name in boundary)


def test_everrun_canonical_governance_events_are_not_reported_unknown() -> None:
    """The EverRun fixture's project_validation x2 and project_scope events are
    canonical governance evidence consumed by conformance; the validator must
    not call them unknown."""
    result = validate_evidence_package_contract(EVERRUN)
    assert result.ok is True
    unknown = [w for w in result.warnings if "unknown event_type" in w]
    assert unknown == []
    assert any("project_validation" in w for w in result.warnings) is False


def test_second_producer_structured_evidence_is_not_reported_unknown() -> None:
    """authority_evidence, budget_evidence, project_validation are canonical;
    only the truly unsupported mcp.tool.result_received stays a warning."""
    result = validate_evidence_package_contract(SECOND_PRODUCER)
    assert result.ok is True
    unknown = [w for w in result.warnings if "unknown event_type" in w]
    assert unknown == [
        "event[3] (event_id 'evt-sp-004') has unknown event_type: "
        "mcp.tool.result_received"
    ]
    assert result.errors == []


def test_structured_governance_evidence_recognition_is_source_neutral(
    tmp_path: Path,
) -> None:
    """Relabelling the producer changes nothing about recognition."""
    events = [
        _event("e1", "run_started"),
        _event("e2", "project_scope", {"status": "clean"}),
        _event("e3", "approval_evidence", {"subject": "s", "decision": "approved"}),
        _event("e4", "authority_evidence", {"actor": "a", "status": "authorized"}),
        _event("e5", "budget_evidence", {"subject": "b", "unit": "u"}),
        _event("e6", "governance_context", {"principal_ref": "p"}),
        _event("e7", "runtime_role", {"name": "judge"}),
    ]
    a = _make_package(tmp_path / "a", events, run_id="run-a")
    b = _make_package(tmp_path / "b", events, run_id="run-b")

    for pkg in (a, b):
        result = validate_evidence_package_contract(pkg)
        assert result.ok is True
        assert result.warnings == []
        assert result.errors == []


def test_truly_unknown_event_type_still_warns(tmp_path: Path) -> None:
    events = [_event("e1", "run_started"), _event("e2", "producer_private_event")]
    pkg = _make_package(tmp_path, events)
    result = validate_evidence_package_contract(pkg)
    assert result.ok is True
    assert any("unknown event_type: producer_private_event" in w for w in result.warnings)


# ── CV2: evidence consistency ──────────────────────────────────────────────


def test_compact_deterministic_contradiction_yields_grounded_finding(
    tmp_path: Path,
) -> None:
    """Two terminal states (run_completed + run_failed) cannot both be true."""
    events = [
        _event("e1", "run_started"),
        _event("e2", "run_completed", {"result": "completed"}),
        _event("e3", "run_failed", {"error": "boom"}),
    ]
    pkg = _make_package(tmp_path, events)
    result = audit_evidence_package(pkg)
    assert result.decision.value == "fail"
    assert result.ok is False
    inconsistent_errors = [e for e in result.errors if "inconsistent_evidence" in e]
    assert len(inconsistent_errors) == 1
    error = inconsistent_errors[0]
    assert "lifecycle_terminal_conflict" in error
    assert error.startswith("inconsistent_evidence[lifecycle_terminal_conflict]")
    assert "run_terminal_state" in error
    assert "[completed, failed]" in error
    assert "(e2, e3)" in error


def test_equivalent_or_non_conflicting_claims_do_not_contradict(tmp_path: Path) -> None:
    """Repeated identical terminal evidence is redundant, not contradictory."""
    events = [
        _event("e1", "run_started"),
        _event("e2", "run_completed", {"result": "completed"}),
        _event("e3", "run_completed", {"result": "completed"}),
    ]
    pkg = _make_package(tmp_path, events)
    result = audit_evidence_package(pkg)
    assert result.decision.value != "fail"
    assert not any("inconsistent_evidence" in e for e in result.errors)


def test_missing_side_is_not_promoted_into_contradiction(tmp_path: Path) -> None:
    """A single terminal event with no conflicting side stays non-contradictory."""
    events = [_event("e1", "run_started"), _event("e2", "run_completed")]
    pkg = _make_package(tmp_path, events)
    result = audit_evidence_package(pkg)
    assert not any("inconsistent_evidence" in e for e in result.errors)
    assert result.ok is True


def test_unsupported_event_type_is_not_interpreted_as_contradiction(
    tmp_path: Path,
) -> None:
    """Unsupported producer-private events never manufacture a contradiction."""
    events = [
        _event("e1", "run_started"),
        _event("e2", "run_completed"),
        _event("e3", "producer_private_event", {"terminal": "failed"}),
    ]
    pkg = _make_package(tmp_path, events)
    result = audit_evidence_package(pkg)
    assert not any("inconsistent_evidence" in e for e in result.errors)
    assert result.decision.value == "warn"  # unknown event still warns


def test_approval_contradiction_is_grounded(tmp_path: Path) -> None:
    """approved and denied for the same (subject, action) contradict."""
    events = [
        _event("e1", "run_started"),
        _event(
            "e2",
            "approval_evidence",
            {"subject": "deploy", "action": "prod", "decision": "approved"},
        ),
        _event(
            "e3",
            "approval_evidence",
            {"subject": "deploy", "action": "prod", "decision": "denied"},
        ),
    ]
    pkg = _make_package(tmp_path, events)
    result = audit_evidence_package(pkg)
    inconsistent_errors = [e for e in result.errors if "inconsistent_evidence" in e]
    assert len(inconsistent_errors) == 1
    error = inconsistent_errors[0]
    assert "approval_decision_conflict" in error
    assert "deploy/prod" in error
    assert "(e2, e3)" in error


def test_authority_contradiction_is_grounded(tmp_path: Path) -> None:
    """authorized and violation for the same (actor, action) contradict."""
    events = [
        _event("e1", "run_started"),
        _event(
            "e2",
            "authority_evidence",
            {"actor": "agent", "action": "write", "status": "authorized"},
        ),
        _event(
            "e3",
            "authority_evidence",
            {"actor": "agent", "action": "write", "status": "violation"},
        ),
    ]
    pkg = _make_package(tmp_path, events)
    result = audit_evidence_package(pkg)
    inconsistent_errors = [e for e in result.errors if "inconsistent_evidence" in e]
    assert len(inconsistent_errors) == 1
    error = inconsistent_errors[0]
    assert "authority_state_conflict" in error
    assert "agent/write" in error
    assert "(e2, e3)" in error


def test_different_subjects_do_not_contradict(tmp_path: Path) -> None:
    """Different subjects/actions with different decisions are independent facts,
    not a contradiction."""
    events = [
        _event("e1", "run_started"),
        _event(
            "e2",
            "approval_evidence",
            {"subject": "deploy", "action": "prod", "decision": "approved"},
        ),
        _event(
            "e3",
            "approval_evidence",
            {"subject": "rollback", "action": "prod", "decision": "denied"},
        ),
    ]
    pkg = _make_package(tmp_path, events)
    result = audit_evidence_package(pkg)
    assert not any("inconsistent_evidence" in e for e in result.errors)


def test_missing_decision_value_is_not_contradictory(tmp_path: Path) -> None:
    """A missing decision field cannot participate in a contradiction."""
    events = [
        _event("e1", "run_started"),
        _event("e2", "approval_evidence", {"subject": "deploy"}),
        _event("e3", "approval_evidence", {"subject": "deploy", "decision": "denied"}),
    ]
    pkg = _make_package(tmp_path, events)
    result = audit_evidence_package(pkg)
    assert not any("inconsistent_evidence" in e for e in result.errors)


def test_detection_is_deterministic_and_serializable(tmp_path: Path) -> None:
    events = [
        _event("e1", "run_started"),
        _event("e2", "run_completed"),
        _event("e3", "run_failed"),
    ]
    first = detect_evidence_inconsistencies(events)
    second = detect_evidence_inconsistencies(events)
    assert first == second
    assert isinstance(first[0], EvidenceInconsistency)
    dumped = json.loads(json.dumps([f.model_dump() for f in first]))
    assert dumped[0]["rule_id"] == "lifecycle_terminal_conflict"
    assert dumped[0]["evidence_ids"] == ["e2", "e3"]


def test_json_report_includes_grounded_inconsistencies(tmp_path: Path) -> None:
    events = [
        _event("e1", "run_started"),
        _event("e2", "run_completed"),
        _event("e3", "run_failed"),
    ]
    pkg = _make_package(tmp_path, events)
    data = audit_result_to_dict(audit_evidence_package(pkg))
    assert data["decision"] == "fail"
    assert data["ok"] is False
    assert data["errors"] == [
        "inconsistent_evidence[lifecycle_terminal_conflict] run_terminal_state: "
        "[completed, failed] (e2, e3)"
    ]


def test_conformance_result_reports_inconsistencies(tmp_path: Path) -> None:
    from ailuros.evidence_conformance import evaluate_evidence_conformance

    events = [
        _event("e1", "run_started"),
        _event("e2", "run_completed"),
        _event("e3", "run_failed"),
    ]
    pkg = _make_package(tmp_path, events)
    result = evaluate_evidence_conformance(pkg)
    assert len(result.inconsistencies) == 1
    assert result.inconsistencies[0].rule_id == "lifecycle_terminal_conflict"


def test_shared_fixtures_carry_no_contradiction() -> None:
    """The accepted production fixtures carry no contradiction. The EverRun
    fixture is now fully canonical (pass); the second producer still warns on
    its genuinely unsupported mcp.tool.result_received event — neither is ever
    escalated to fail on fabricated grounds."""
    everrun = audit_evidence_package(EVERRUN)
    assert not any("inconsistent_evidence" in e for e in everrun.errors)
    assert everrun.decision.value == "pass"
    assert everrun.ok is True

    second = audit_evidence_package(SECOND_PRODUCER)
    assert not any("inconsistent_evidence" in e for e in second.errors)
    assert second.decision.value == "warn"
    assert second.ok is True


def test_source_relabel_does_not_change_consistency(tmp_path: Path) -> None:
    relabeled = tmp_path / "relabeled"
    shutil.copytree(SECOND_PRODUCER, relabeled)
    manifest = json.loads((relabeled / "manifest.json").read_text(encoding="utf-8"))
    manifest["source"] = "zzz-unseen-producer"
    _write_json(relabeled / "manifest.json", manifest)

    baseline = audit_evidence_package(SECOND_PRODUCER)
    relabeled_result = audit_evidence_package(relabeled)
    baseline_errs = [e for e in baseline.errors if "inconsistent_evidence" in e]
    relabeled_errs = [
        e for e in relabeled_result.errors if "inconsistent_evidence" in e
    ]
    assert baseline_errs == relabeled_errs
    assert baseline.decision == relabeled_result.decision
