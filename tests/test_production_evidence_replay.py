"""Deterministic replay proof (8076) against the production-derived fixture.

The fixture is `fixtures/runtime-evidence/everrun-postfix-minimal/` (run
`run-20260824-004751`), the privacy-screened minimal distillation accepted by
8070/8071 from the real 8065/8066 EverRun evidence. The fixture is replayed
twice, independently, through the same production pipeline
(validate -> load -> ingest -> rebuild -> governed report) into two separate
disposable SQLite storage instances. Both replays must produce identical
canonical governance facts and identical evidence attribution.

Red lines honored here:
- Source evidence is never mutated: the fixture bytes are byte-identical
  before and after every replay.
- Unknowns and warnings are never suppressed: lifecycle stays `running` (no
  `run_completed` in the fixture), outcome/governed outcome stay `unknown`,
  and the `unknown event_type` registry-gap warnings remain present.
- No runtime orchestration is added; replay is fully offline on disposable
  storage.
"""

from __future__ import annotations

from pathlib import Path

from ailuros.adapters.evidence_package import (
    ImportStatus,
    audit_evidence_package,
    ingest_evidence_package,
    load_evidence_package,
    validate_evidence_package_contract,
)
from ailuros.execution_report import build_run_report
from ailuros.projection import rebuild_projections_and_signals
from ailuros.storage.sqlite_storage import SQLiteStorage

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
FIXTURE = REPO_ROOT / "fixtures" / "runtime-evidence" / "everrun-postfix-minimal"

RUN_ID = "run-20260824-004751"


def _new_storage(tmp_path: Path, name: str) -> SQLiteStorage:
    storage = SQLiteStorage(tmp_path / f"{name}.db")
    storage.init()
    return storage


def _replay(tmp_path: Path, name: str):
    """Run the canonical production pipeline once on a disposable storage.

    Returns the (projection, signals, report, audit, stored_events) produced by
    an independent replay. Each replay loads the fixture from disk again, so the
    two replays share no state at all.
    """
    result = validate_evidence_package_contract(FIXTURE)
    assert result.ok is True
    assert result.errors == []

    audit = audit_evidence_package(FIXTURE)
    assert audit.ok is True

    package = load_evidence_package(FIXTURE)
    storage = _new_storage(tmp_path, name)
    ingest = ingest_evidence_package(storage, package)
    assert ingest.status == ImportStatus.CREATED
    assert ingest.events_imported == len(package.events)

    proj, signals = rebuild_projections_and_signals(storage, package.run_id)
    report = build_run_report(proj, signals)
    stored_events = storage.list_events(package.run_id)
    return proj, signals, report, audit, stored_events


def _canonical_facts(proj, signals, report) -> dict:
    """Extract the canonical governance facts that must be replay-deterministic.

    Covers governance semantics (lifecycle, native outcome, governed outcome,
    validation, scope, decisions, coverage, changes, why-stopped) and evidence
    attribution (evidence refs). `GovernanceSignal.created_at` is deliberately
    excluded: it is stamped with `datetime.now(UTC)` at signal build time and
    carries no governance semantics or evidence attribution.
    """
    return {
        "run_id": proj.run_id,
        "lifecycle": proj.lifecycle.value,
        "outcome": proj.outcome.value,
        "governed_outcome": report.governed_outcome,
        "validation": proj.validation.value,
        "scope": proj.scope.value,
        "report_validation": report.validation,
        "report_scope": report.scope,
        "decision_count": proj.decision_count,
        "decisions": [
            (d.domain, d.decision, d.projected_domain) for d in proj.decisions
        ],
        "governance_coverage": {
            "authority": proj.governance_coverage.authority.value,
            "approval": proj.governance_coverage.approval.value,
            "budget": proj.governance_coverage.budget.value,
            "validation": proj.governance_coverage.validation.value,
            "scope": proj.governance_coverage.scope.value,
        },
        "changes": [c.description for c in proj.changes],
        "authority_records": [
            (r.state.value, r.subject, [ref.event_id for ref in r.evidence_refs])
            for r in proj.authority_records
        ],
        "approval_records": [
            (r.state.value, r.subject, [ref.event_id for ref in r.evidence_refs])
            for r in proj.approval_records
        ],
        "budget_records": [
            (r.state.value, r.subject, [ref.event_id for ref in r.evidence_refs])
            for r in proj.budget_records
        ],
        "event_count": proj.event_count,
        "step_count": proj.step_count,
        "started_at": proj.started_at.isoformat(),
        "completed_at": (
            proj.completed_at.isoformat() if proj.completed_at is not None else None
        ),
        "scope_ref": proj.scope_ref,
        "why_stopped": report.why_stopped,
        "decision_reasons": list(report.decision_reasons),
        "signal_types": [(s.type, s.severity, s.subject) for s in signals],
        "signal_evidence": [
            (s.type, sorted(ref.event_id for ref in s.evidence_refs)) for s in signals
        ],
        "evidence_refs": sorted(ref.event_id for ref in proj.evidence_refs),
        "report_evidence_refs": sorted(ref.event_id for ref in report.evidence_refs),
    }


def _fixture_bytes() -> dict[str, bytes]:
    return {
        "manifest.json": (FIXTURE / "manifest.json").read_bytes(),
        "timeline.json": (FIXTURE / "timeline.json").read_bytes(),
    }


# ── T1: the replay fixture is the 8070/8071 production-derived fixture ───────


def test_replay_uses_the_8070_8071_production_derived_fixture(tmp_path) -> None:
    result = validate_evidence_package_contract(FIXTURE)
    assert result.ok is True
    assert result.errors == []
    assert result.source == "everrun"
    assert result.run_id == RUN_ID
    assert result.schema_version == "ailuros.timeline.v1"
    assert result.events_count == 5


def test_fixture_unknown_event_type_warnings_are_not_suppressed(tmp_path) -> None:
    """The accepted fixture keeps the `unknown event_type` registry-gap warnings
    the raw accepted package produced (project_validation x2, project_scope x1).
    Suppressing them to make outputs match is a red line and must not happen."""
    result = validate_evidence_package_contract(FIXTURE)
    assert result.ok is True
    unknown = [w for w in result.warnings if "unknown event_type" in w]
    assert len(unknown) == 3
    assert any("project_validation" in w for w in unknown)
    assert any("project_scope" in w for w in unknown)


def test_replay_does_not_mutate_source_evidence(tmp_path) -> None:
    """Red line: source evidence is never mutated. The fixture bytes must be
    byte-identical before and after an independent replay through the
    production pipeline."""
    before = _fixture_bytes()
    _replay(tmp_path, "evidence-no-mutate")
    after = _fixture_bytes()
    assert after == before


# ── T2/T3: two independent replays produce identical canonical facts ────────


def test_independent_double_replay_produces_identical_canonical_facts(
    tmp_path,
) -> None:
    """Two separate disposable storage instances, each loaded/ingested/rebuild/
    reported independently from the same on-disk fixture, must produce identical
    canonical governance facts (lifecycle, native outcome, governed outcome,
    validation, scope, decisions, coverage, changes, why-stopped) and identical
    evidence attribution (evidence refs)."""
    replay_a = _replay(tmp_path, "replay-a")
    replay_b = _replay(tmp_path, "replay-b")

    facts_a = _canonical_facts(*replay_a[:3])
    facts_b = _canonical_facts(*replay_b[:3])
    assert facts_a == facts_b


def test_independent_double_replay_evidence_attribution_resolves_identically(
    tmp_path,
) -> None:
    """Every projection/report evidence ref must resolve to the same stored
    event id in both storages, proving attribution is deterministic and the
    refs are not dangling or storage-dependent."""
    replay_a = _replay(tmp_path, "resolve-a")
    replay_b = _replay(tmp_path, "resolve-b")

    proj_a, _, report_a, _, events_a = replay_a
    proj_b, _, report_b, _, events_b = replay_b

    ids_a = {e.event_id for e in events_a}
    ids_b = {e.event_id for e in events_b}
    assert ids_a == ids_b

    refs_a = sorted(ref.event_id for ref in proj_a.evidence_refs)
    refs_b = sorted(ref.event_id for ref in proj_b.evidence_refs)
    assert refs_a == refs_b
    assert refs_a == sorted(ref.event_id for ref in report_a.evidence_refs)
    assert refs_b == sorted(ref.event_id for ref in report_b.evidence_refs)

    for ref in refs_a:
        assert ref in ids_a
        assert ref in ids_b


# ── Red line: unknowns stay unknown, nothing is promoted to clean ────────────


def test_replay_keeps_unknowns_stable_across_both_replays(tmp_path) -> None:
    replay_a = _replay(tmp_path, "unknown-a")
    replay_b = _replay(tmp_path, "unknown-b")

    for proj, _, report, audit, _ in (replay_a, replay_b):
        assert proj.lifecycle.value == "running"
        assert proj.outcome.value == "unknown"
        assert report.governed_outcome == "unknown"
        assert proj.governance_coverage.authority.value == "unknown"
        assert proj.governance_coverage.approval.value == "unknown"
        assert proj.governance_coverage.budget.value == "unknown"
        assert report.why_stopped == "execution_control: human_review"
        assert report.governed_outcome != "clean_success"
        assert audit.decision == "warn"


# ── T3: intentional exclusion is limited to incidental non-semantic fields ──


def test_only_excluded_field_is_governance_signal_created_at(tmp_path) -> None:
    """Document the intentional exclusion: `GovernanceSignal.created_at` is
    stamped with `datetime.now(UTC)` at build time and carries no governance
    semantics or evidence attribution. Every other canonical field on the
    projection, report, and signal models is compared exactly between replays."""
    from ailuros.signals import GovernanceSignal

    replay_a = _replay(tmp_path, "exclude-a")
    replay_b = _replay(tmp_path, "exclude-b")

    for proj, signals, report, _, _ in (replay_a, replay_b):
        assert type(proj).model_fields.keys() == {
            "run_id",
            "source",
            "schema_version",
            "lifecycle",
            "outcome",
            "validation",
            "scope",
            "started_at",
            "completed_at",
            "scope_ref",
            "step_count",
            "decision_count",
            "event_count",
            "roles",
            "changes",
            "decisions",
            "evidence_refs",
            "governance_context",
            "approval_records",
            "budget_records",
            "authority_records",
            "governance_coverage",
            "version",
        }
        assert type(report).model_fields.keys() == {
            "run_id",
            "lifecycle",
            "outcome",
            "native_outcome",
            "governed_outcome",
            "aggregate_governed_outcome",
            "validation",
            "scope",
            "governance_coverage",
            "scope_outcomes",
            "why_stopped",
            "outcome_reasons",
            "governed_outcome_reasons",
            "signal_summaries",
            "decision_reasons",
            "changes",
            "roles",
            "evidence_refs",
            "step_count",
            "decision_count",
            "event_count",
            "started_at",
            "completed_at",
        }
        for signal in signals:
            assert set(type(signal).model_fields) == {
                "signal_id",
                "run_id",
                "type",
                "severity",
                "subject",
                "scope_ref",
                "details",
                "evidence_refs",
                "rule_version",
                "created_at",
            }
            assert signal.created_at is not None

    # Both evidence-integrity findings are canonical; only their incidental
    # creation timestamps differ between otherwise identical replays.
    expected_signal_types = [
        "missing_run_terminal_evidence",
        "temporal_integrity",
    ]
    assert all(
        [signal.type for signal in signals] == expected_signal_types
        for _, signals, _, _, _ in (replay_a, replay_b)
    )

    def _dump_excluding_created_at(proj, signals, report) -> dict:
        return {
            "projection": proj.model_dump(),
            "signals": [
                {k: v for k, v in s.model_dump().items() if k != "created_at"}
                for s in signals
            ],
            "report": report.model_dump(),
        }

    assert _dump_excluding_created_at(*replay_a[:3]) == _dump_excluding_created_at(
        *replay_b[:3]
    )
    assert GovernanceSignal is not None
