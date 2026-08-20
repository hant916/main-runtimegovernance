from datetime import UTC, datetime

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
from ailuros.regression import (
    GovernanceDimension,
    GovernanceTransition,
    compare_governance_projections,
)


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
