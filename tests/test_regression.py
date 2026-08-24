from datetime import UTC, datetime
from pathlib import Path

from ailuros.adapters.evidence_package import (
    ingest_evidence_package,
    load_evidence_package,
)
from ailuros.core.execution import (
    ApprovalRecord,
    ApprovalState,
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
from ailuros.storage.sqlite_storage import SQLiteStorage

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
EVERRUN_POSTFIX_MINIMAL = (
    REPO_ROOT / "fixtures" / "runtime-evidence" / "everrun-postfix-minimal"
)
SECOND_PRODUCER = REPO_ROOT / "fixtures" / "runtime-evidence" / "second-producer"


def _projection(
    run_id: str,
    *,
    source: str = "everrun",
    lifecycle: Lifecycle = Lifecycle.COMPLETED,
    outcome: Outcome = Outcome.SUCCESS,
    validation: Validation = Validation.PASSED,
    scope: Scope = Scope.CLEAN,
    decisions: list[DecisionSummary] | None = None,
    approvals: list[ApprovalRecord] | None = None,
    authorities: list[AuthorityRecord] | None = None,
    budgets: list[BudgetRecord] | None = None,
    coverage: GovernanceCoverage | None = None,
) -> ExecutionProjection:
    now = datetime.now(UTC)
    return ExecutionProjection(
        run_id=run_id,
        source=source,
        schema_version="1.0",
        lifecycle=lifecycle,
        outcome=outcome,
        validation=validation,
        scope=scope,
        started_at=now,
        completed_at=now,
        decisions=decisions or [],
        approval_records=approvals or [],
        authority_records=authorities or [],
        budget_records=budgets or [],
        governance_coverage=coverage or GovernanceCoverage(),
    )


def _transition(result, dimension: GovernanceDimension) -> GovernanceTransition:
    return next(item.transition for item in result.dimensions if item.dimension == dimension)


def test_governance_delta_detects_regressions_across_available_facts() -> None:
    coverage = GovernanceCoverage(
        authority="evaluated",
        approval="evaluated",
        budget="evaluated",
        validation="evaluated",
        scope="evaluated",
    )
    baseline = _projection(
        "run-before",
        approvals=[
            ApprovalRecord(
                subject="release",
                state=ApprovalState.APPROVED,
                timestamp=datetime.now(UTC),
            )
        ],
        authorities=[AuthorityRecord(actor="agent", state=AuthorityState.AUTHORIZED)],
        budgets=[BudgetRecord(subject="release", unit="usd", status="within_limit")],
        coverage=coverage,
    )
    current = _projection(
        "run-after",
        lifecycle=Lifecycle.FAILED,
        outcome=Outcome.FAILED,
        validation=Validation.FAILED,
        scope=Scope.VIOLATED,
        approvals=[
            ApprovalRecord(
                subject="release",
                state=ApprovalState.DENIED,
                timestamp=datetime.now(UTC),
            )
        ],
        authorities=[AuthorityRecord(actor="agent", state=AuthorityState.VIOLATION)],
        budgets=[BudgetRecord(subject="release", unit="usd", limit=10, consumed=11)],
        coverage=coverage,
    )

    result = compare_governance_projections(baseline, current)

    assert result.baseline_run_id == "run-before"
    assert result.current_run_id == "run-after"
    for dimension in (
        GovernanceDimension.NATIVE_OUTCOME,
        GovernanceDimension.GOVERNED_OUTCOME,
        GovernanceDimension.VALIDATION,
        GovernanceDimension.SCOPE,
        GovernanceDimension.AUTHORITY,
        GovernanceDimension.APPROVAL,
        GovernanceDimension.BUDGET,
    ):
        assert _transition(result, dimension) == GovernanceTransition.REGRESSED


def test_governance_delta_detects_improvement_and_ignores_producer_identity() -> None:
    coverage = GovernanceCoverage(validation="evaluated", scope="evaluated")
    baseline = _projection(
        "run-before",
        source="first-producer",
        validation=Validation.FAILED,
        scope=Scope.VIOLATED,
        coverage=coverage,
    )
    current = _projection(
        "run-after",
        source="second-producer",
        validation=Validation.PASSED,
        scope=Scope.CLEAN,
        coverage=coverage,
    )

    result = compare_governance_projections(baseline, current)

    assert _transition(result, GovernanceDimension.VALIDATION) == GovernanceTransition.IMPROVED
    assert _transition(result, GovernanceDimension.SCOPE) == GovernanceTransition.IMPROVED
    assert _transition(result, GovernanceDimension.GOVERNED_OUTCOME) == (
        GovernanceTransition.UNCHANGED
    )


def test_governance_delta_ignores_source_identity_variation() -> None:
    coverage = GovernanceCoverage(validation="evaluated", scope="evaluated")
    baseline = _projection("run-before", source="producer-a", coverage=coverage)
    current = _projection("run-after", source="producer-b", coverage=coverage)
    cross_source = compare_governance_projections(baseline, current)

    same_source_baseline = _projection("run-before", source="producer-a", coverage=coverage)
    same_source_current = _projection("run-after", source="producer-a", coverage=coverage)
    same_source = compare_governance_projections(same_source_baseline, same_source_current)

    for item in same_source.dimensions:
        assert item.baseline == item.current
        assert item.transition == (
            GovernanceTransition.UNKNOWN
            if item.baseline == "unknown"
            else GovernanceTransition.UNCHANGED
        )
    assert [
        (item.dimension, item.baseline, item.current, item.transition)
        for item in cross_source.dimensions
    ] == [
        (item.dimension, item.baseline, item.current, item.transition)
        for item in same_source.dimensions
    ]


def test_governance_delta_ignores_run_id_variation() -> None:
    coverage = GovernanceCoverage(validation="evaluated", scope="evaluated")
    baseline = _projection("run-0001", coverage=coverage)
    current = _projection("run-0002", coverage=coverage)

    result = compare_governance_projections(baseline, current)

    assert result.baseline_run_id == "run-0001"
    assert result.current_run_id == "run-0002"
    for item in result.dimensions:
        assert item.baseline == item.current
        assert item.transition == (
            GovernanceTransition.UNKNOWN
            if item.baseline == "unknown"
            else GovernanceTransition.UNCHANGED
        )


def test_governance_delta_preserves_unknown_transitions() -> None:
    baseline = _projection("run-before", validation=Validation.UNKNOWN)
    current = _projection("run-after", validation=Validation.PASSED)

    result = compare_governance_projections(baseline, current)

    assert _transition(result, GovernanceDimension.VALIDATION) == GovernanceTransition.UNKNOWN
    assert _transition(result, GovernanceDimension.VALIDATION_COVERAGE) == (
        GovernanceTransition.UNKNOWN
    )


def test_governance_delta_preserves_incomparable_transitions() -> None:
    baseline = _projection(
        "run-before",
        decisions=[DecisionSummary(domain="runtime", decision="block")],
        outcome=Outcome.BLOCKED,
    )
    current = _projection(
        "run-after",
        lifecycle=Lifecycle.FAILED,
        outcome=Outcome.FAILED,
    )

    result = compare_governance_projections(baseline, current)

    assert _transition(result, GovernanceDimension.NATIVE_OUTCOME) == (
        GovernanceTransition.INCOMPARABLE
    )
    assert _transition(result, GovernanceDimension.GOVERNED_OUTCOME) == (
        GovernanceTransition.INCOMPARABLE
    )


def test_governance_delta_real_everrun_pair_transition_matrix() -> None:
    coverage = GovernanceCoverage(validation="evaluated", scope="evaluated")
    baseline = _projection(
        "run-20260824-004751",
        lifecycle=Lifecycle.RUNNING,
        outcome=Outcome.UNKNOWN,
        decisions=[
            DecisionSummary(domain="execution_control", decision="human_review")
        ],
        coverage=coverage,
    )
    current = _projection(
        "run-20260824-011708",
        lifecycle=Lifecycle.RUNNING,
        outcome=Outcome.UNKNOWN,
        decisions=[
            DecisionSummary(domain="execution_control", decision="accept"),
            DecisionSummary(domain="execution_control", decision="accept"),
            DecisionSummary(domain="execution_control", decision="continue"),
        ],
        coverage=coverage,
    )

    result = compare_governance_projections(baseline, current)

    assert result.baseline_run_id == "run-20260824-004751"
    assert result.current_run_id == "run-20260824-011708"
    facts = {
        item.dimension: (item.baseline, item.current, item.transition)
        for item in result.dimensions
    }
    unchanged = GovernanceTransition.UNCHANGED
    unknown = GovernanceTransition.UNKNOWN
    assert facts[GovernanceDimension.VALIDATION] == ("passed", "passed", unchanged)
    assert facts[GovernanceDimension.SCOPE] == ("clean", "clean", unchanged)
    assert facts[GovernanceDimension.VALIDATION_COVERAGE] == (
        "evaluated",
        "evaluated",
        unchanged,
    )
    assert facts[GovernanceDimension.SCOPE_COVERAGE] == (
        "evaluated",
        "evaluated",
        unchanged,
    )
    for dimension in (
        GovernanceDimension.NATIVE_OUTCOME,
        GovernanceDimension.GOVERNED_OUTCOME,
        GovernanceDimension.AUTHORITY,
        GovernanceDimension.APPROVAL,
        GovernanceDimension.BUDGET,
        GovernanceDimension.AUTHORITY_COVERAGE,
        GovernanceDimension.APPROVAL_COVERAGE,
        GovernanceDimension.BUDGET_COVERAGE,
    ):
        assert facts[dimension] == ("unknown", "unknown", unknown)


# ── canonical producer parity: regression read-model is source-neutral ───────


def _project_from_fixture(tmp_path, fixture: Path):
    storage = SQLiteStorage(tmp_path / f"{fixture.name}.db")
    storage.init()
    package = load_evidence_package(fixture)
    ingest_evidence_package(storage, package)
    projection, _ = rebuild_projections_and_signals(storage, package.run_id)
    return projection


def test_canonical_everrun_and_second_producer_regression_is_source_label_inert(
    tmp_path,
) -> None:
    """T2/T1: both canonical fixtures travel the shared load -> ingest -> rebuild
    path, and their projections feed the regression read-model. Relabeling only
    the source leaves the full 12-dimension transition matrix unchanged, proving
    the comparator reads facts, never producer identity."""
    everrun = _project_from_fixture(tmp_path, EVERRUN_POSTFIX_MINIMAL)
    second = _project_from_fixture(tmp_path, SECOND_PRODUCER)

    everrun_relabeled = everrun.model_copy(update={"source": "second-producer"})
    second_relabeled = second.model_copy(update={"source": "everrun"})

    baseline = compare_governance_projections(everrun, second)
    relabeled = compare_governance_projections(everrun_relabeled, second_relabeled)

    assert len(baseline.dimensions) == 12
    assert [
        (d.dimension, d.baseline, d.current, d.transition)
        for d in baseline.dimensions
    ] == [
        (d.dimension, d.baseline, d.current, d.transition)
        for d in relabeled.dimensions
    ]
    assert baseline.baseline_run_id == everrun.run_id
    assert baseline.current_run_id == second.run_id


def test_canonical_fixture_self_delta_under_relabel_is_identity(tmp_path) -> None:
    """A projection compared against its own source-relabeled clone must yield
    only unchanged/unknown transitions: source label alone cannot manufacture a
    regression or improvement."""
    everrun = _project_from_fixture(tmp_path, EVERRUN_POSTFIX_MINIMAL)
    second = _project_from_fixture(tmp_path, SECOND_PRODUCER)

    for projection in (everrun, second):
        clone = projection.model_copy(update={"source": "relabeled-producer"})
        delta = compare_governance_projections(projection, clone)
        for item in delta.dimensions:
            assert item.baseline == item.current
            assert item.transition in {
                GovernanceTransition.UNCHANGED,
                GovernanceTransition.UNKNOWN,
            }
