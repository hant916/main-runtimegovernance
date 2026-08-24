"""Bounded production-backed governance regression corpus.

The corpus lives in ``fixtures/governance-regression/cases/*.json``. Each case is
a real or production-derived comparable pair that pre-declares, before the
comparator is run, the baseline fact, current fact, expected transition, and
evidence refs for every supported dimension.

Mapping to the pack steps:

- T1  inventories the corpus and rejects pairs without a defensible comparison
       context (``test_corpus_inventory_rejects_undefended_pairs``,
       ``test_corpus_anchors_real_8067_production_pair``).
- T2  validates every case pre-declares baseline fact, current fact, expected
       transition, and evidence refs for all supported dimensions
       (``test_corpus_cases_predeclare_facts_transitions_and_evidence``).
- T3  runs the source-neutral comparator over each case and retains
       UNKNOWN/INCOMPARABLE where required; fixture-backed runs are additionally
       projected through the production load/ingest/rebuild path
       (``test_corpus_comparator_matches_predeclared_matrix``,
       ``test_corpus_fixture_sides_project_via_production_path``).
- T4  reports enum coverage gaps: dimensions and transitions for which no real
       case exists, without creating synthetic substitutes
       (``test_corpus_reports_coverage_gaps``).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ailuros.adapters.evidence_package import (
    ingest_evidence_package,
    load_evidence_package,
)
from ailuros.core.execution import (
    AuthorityRecord,
    AuthorityState,
    BudgetRecord,
    DecisionSummary,
    ExecutionProjection,
    GovernanceCoverage,
    Lifecycle,
    Outcome,
    Scope,
    Validation,
)
from ailuros.projection import rebuild_projections_and_signals
from ailuros.regression import (
    GovernanceDimension,
    GovernanceTransition,
    compare_governance_projections,
)
from ailuros.regression.governance_delta import _facts
from ailuros.storage.sqlite_storage import SQLiteStorage

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
CORPUS_DIR = REPO_ROOT / "fixtures" / "governance-regression" / "cases"

ALL_DIMENSIONS: tuple[GovernanceDimension, ...] = tuple(GovernanceDimension)
ALL_TRANSITIONS: set[str] = {transition.value for transition in GovernanceTransition}


def _load_cases() -> list[dict]:
    files = sorted(CORPUS_DIR.glob("*.json"))
    assert files, f"no corpus cases found under {CORPUS_DIR}"
    return [json.loads(path.read_text(encoding="utf-8")) for path in files]


def _load_case_params():
    for path in sorted(CORPUS_DIR.glob("*.json")):
        yield pytest.param(
            json.loads(path.read_text(encoding="utf-8")), id=path.stem
        )


# ── T1: inventory real comparable pairs; reject undefended pairs ─────────────


def test_corpus_inventory_rejects_undefended_pairs() -> None:
    """Every corpus case must state an explicit comparability rationale, source
    evidence, and evidence refs on both sides. A case without them has no
    defensible comparison context and must be rejected, not silently compared."""
    for case in _load_cases():
        assert case["comparability_rationale"].strip(), (
            f"{case['name']}: missing comparability rationale"
        )
        assert case["provenance"]["source_evidence"].strip(), (
            f"{case['name']}: missing source evidence"
        )
        for side in ("baseline", "current"):
            assert case[side]["evidence_refs"], (
                f"{case['name']}: {side} has no evidence refs"
            )


def test_corpus_anchors_real_8067_production_pair() -> None:
    """T1: the corpus is anchored on the 8067/8072 real EverRun pair. Its run ids
    must be the accepted baseline/current pair, and the accepted_reason recorded
    in the open issue must be carried through."""
    real = [c for c in _load_cases() if c["kind"] == "real_production_pair"]
    assert len(real) == 1
    case = real[0]
    assert case["baseline"]["run_id"] == "run-20260824-004751"
    assert case["current"]["run_id"] == "run-20260824-011708"
    assert "8067.prove-real-governance-regression-from-everrun-runs" in case[
        "provenance"
    ]["packs"]
    assert (
        case["provenance"]["accepted_reason"]
        == "planner_proposed_accept_and_no_blocking_rule_triggered"
    )


# ── T2: pre-declared expectations per supported dimension ────────────────────


def test_corpus_cases_predeclare_facts_transitions_and_evidence() -> None:
    """T2: every case pre-declares, for every supported dimension, the baseline
    fact, current fact, expected transition, and the raw projection facts plus
    evidence refs needed to reproduce the comparison."""
    for case in _load_cases():
        dims = [row["dimension"] for row in case["expected"]]
        assert dims == [dimension.value for dimension in ALL_DIMENSIONS], (
            f"{case['name']}: expected matrix must cover every supported dimension"
            " in canonical order"
        )
        for row in case["expected"]:
            assert row["baseline"] and row["current"], (
                f"{case['name']}: empty fact for {row['dimension']}"
            )
            assert row["transition"] in ALL_TRANSITIONS, (
                f"{case['name']}: invalid transition {row['transition']!r}"
            )
        for side in ("baseline", "current"):
            facts = case[side]["facts"]
            assert facts["run_id"] == case[side]["run_id"]
            for field in ("lifecycle", "outcome", "validation", "scope"):
                assert field in facts, (
                    f"{case['name']}: {side} facts missing {field!r}"
                )
            assert "governance_coverage" in facts, (
                f"{case['name']}: {side} facts missing governance_coverage"
            )


# ── T3: run corpus tests against the source-neutral comparator ───────────────


def _projection_from_facts(facts: dict) -> ExecutionProjection:
    now = datetime.now(UTC)
    coverage_values = facts.get("governance_coverage", {})
    coverage = GovernanceCoverage(
        authority=coverage_values.get("authority", "unknown"),
        approval=coverage_values.get("approval", "unknown"),
        budget=coverage_values.get("budget", "unknown"),
        validation=coverage_values.get("validation", "unknown"),
        scope=coverage_values.get("scope", "unknown"),
    )
    return ExecutionProjection(
        run_id=facts["run_id"],
        source="everrun",
        schema_version="1.0",
        lifecycle=Lifecycle(facts["lifecycle"]),
        outcome=Outcome(facts["outcome"]),
        validation=Validation(facts["validation"]),
        scope=Scope(facts["scope"]),
        started_at=now,
        decisions=[
            DecisionSummary(domain=decision["domain"], decision=decision["decision"])
            for decision in facts.get("decisions", [])
        ],
        authority_records=[
            AuthorityRecord(actor=record["actor"], state=AuthorityState(record["state"]))
            for record in facts.get("authority_records", [])
        ],
        budget_records=[
            BudgetRecord(
                subject=record["subject"],
                unit=record.get("unit", "usd"),
                status=record.get("status", "unknown"),
            )
            for record in facts.get("budget_records", [])
        ],
        governance_coverage=coverage,
    )


def _expected_facts_by_side(case: dict) -> tuple[dict[str, str], dict[str, str]]:
    baseline: dict[str, str] = {}
    current: dict[str, str] = {}
    for row in case["expected"]:
        baseline[row["dimension"]] = row["baseline"]
        current[row["dimension"]] = row["current"]
    return baseline, current


@pytest.mark.parametrize("case", _load_case_params())
def test_corpus_comparator_matches_predeclared_matrix(case: dict) -> None:
    """T3: the source-neutral comparator reproduces the pre-declared transition
    matrix for every corpus case. UNKNOWN/INCOMPARABLE transitions are retained
    exactly as pre-declared; no fact is inferred."""
    baseline = _projection_from_facts(case["baseline"]["facts"])
    current = _projection_from_facts(case["current"]["facts"])

    expected = {
        row["dimension"]: (row["baseline"], row["current"], row["transition"])
        for row in case["expected"]
    }

    result = compare_governance_projections(baseline, current)

    assert result.baseline_run_id == case["baseline"]["run_id"]
    assert result.current_run_id == case["current"]["run_id"]
    assert len(result.dimensions) == len(ALL_DIMENSIONS)
    assert [item.dimension for item in result.dimensions] == list(ALL_DIMENSIONS)

    actual = {
        item.dimension.value: (item.baseline, item.current, item.transition.value)
        for item in result.dimensions
    }
    assert actual == expected, (
        f"Corpus case '{case['name']}' did not match its pre-declared matrix:\n"
        f"  expected: {expected}\n"
        f"  actual:   {actual}"
    )


@pytest.mark.parametrize("case", _load_case_params())
def test_corpus_fixture_sides_project_via_production_path(
    case: dict, tmp_path: Path
) -> None:
    """T3: for every fixture-backed side, the projection is rebuilt through the
    production load -> ingest -> rebuild path and its derived canonical facts
    must equal the pre-declared fact column. This ties each recorded fact to the
    on-disk production evidence instead of trusting hand-written facts."""
    expected_baseline, expected_current = _expected_facts_by_side(case)
    for side, expected in (
        ("baseline", expected_baseline),
        ("current", expected_current),
    ):
        fixture = case[side].get("fixture")
        if not fixture:
            continue
        fixture_path = REPO_ROOT / fixture
        assert fixture_path.is_dir(), (
            f"{case['name']}: {side} fixture {fixture!r} does not exist"
        )

        storage = SQLiteStorage(tmp_path / f"{case['name']}-{side}.db")
        storage.init()
        package = load_evidence_package(fixture_path)
        ingest_evidence_package(storage, package)
        projection, _ = rebuild_projections_and_signals(storage, package.run_id)

        actual = {
            dimension.value: value for dimension, value in _facts(projection).items()
        }
        assert actual == expected, (
            f"{case['name']}: {side} fixture ({package.run_id}) derived facts do not"
            f" match the pre-declared fact column:\n  expected: {expected}\n"
            f"  actual:   {actual}"
        )


# ── T4: coverage gaps ─────────────────────────────────────────────────────────

# Ranked transitions (improved / regressed / incomparable) and any
# authority/approval/budget fact ordering have NO real production case yet. The
# corpus must not synthesize substitutes, so these gaps are asserted rather than
# filled.
_UNPROVEN_TRANSITIONS = {
    GovernanceTransition.IMPROVED,
    GovernanceTransition.REGRESSED,
    GovernanceTransition.INCOMPARABLE,
}
_EVIDENCE_MISSING_DIMENSIONS = {
    GovernanceDimension.AUTHORITY,
    GovernanceDimension.APPROVAL,
    GovernanceDimension.BUDGET,
    GovernanceDimension.AUTHORITY_COVERAGE,
    GovernanceDimension.APPROVAL_COVERAGE,
    GovernanceDimension.BUDGET_COVERAGE,
}


def test_corpus_reports_coverage_gaps() -> None:
    """T4: list the enum transitions and dimensions for which no real case exists
    without creating synthetic substitutes. Adding a real case that proves a
    ranked transition requires updating this gap declaration explicitly."""
    cases = _load_cases()
    covered: dict[str, set[str]] = {}
    for case in cases:
        for row in case["expected"]:
            covered.setdefault(row["dimension"], set()).add(row["transition"])

    for dimension, transitions in covered.items():
        for proven in _UNPROVEN_TRANSITIONS:
            assert proven.value not in transitions, (
                f"corpus case claims {proven.value} for {dimension}, but no real "
                "production case proves that ordering"
            )
    for dimension in _EVIDENCE_MISSING_DIMENSIONS:
        assert covered.get(dimension.value, set()) <= {
            GovernanceTransition.UNKNOWN.value
        }, (
            f"corpus case orders {dimension.value} facts, but no real case has "
            "evaluated records on both sides of a pair"
        )

    # Explicit gap report (documentation surface, not synthetic substitutes):
    # - improved / regressed / incomparable: no real case exists for any dimension.
    # - authority / approval / budget (fact and coverage): only unknown/unknown
    #   transitions exist; no real case has evaluated records on both sides.
    # These gaps are asserted above and must be updated only when a real case
    # proves the corresponding ordering.
