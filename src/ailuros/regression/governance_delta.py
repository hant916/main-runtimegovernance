"""Deterministic, source-neutral governance deltas between run projections."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ailuros._compat import StrEnum
from ailuros.core.execution import (
    ApprovalRecord,
    AuthorityRecord,
    BudgetRecord,
    CoverageState,
    ExecutionProjection,
)
from ailuros.projection import derive_native_outcome


class GovernanceDimension(StrEnum):
    NATIVE_OUTCOME = "native_outcome"
    GOVERNED_OUTCOME = "governed_outcome"
    VALIDATION = "validation"
    SCOPE = "scope"
    AUTHORITY = "authority"
    APPROVAL = "approval"
    BUDGET = "budget"
    AUTHORITY_COVERAGE = "authority_coverage"
    APPROVAL_COVERAGE = "approval_coverage"
    BUDGET_COVERAGE = "budget_coverage"
    VALIDATION_COVERAGE = "validation_coverage"
    SCOPE_COVERAGE = "scope_coverage"


class GovernanceTransition(StrEnum):
    IMPROVED = "improved"
    REGRESSED = "regressed"
    UNCHANGED = "unchanged"
    UNKNOWN = "unknown"
    INCOMPARABLE = "incomparable"


class GovernanceDimensionDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: GovernanceDimension
    baseline: str
    current: str
    transition: GovernanceTransition


class GovernanceRegressionDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseline_run_id: str
    current_run_id: str
    dimensions: list[GovernanceDimensionDelta]


_DIMENSION_ORDER: tuple[GovernanceDimension, ...] = tuple(GovernanceDimension)
_OUTCOME_RANKS = {"success": 4, "partial": 3, "review_required": 2, "blocked": 1, "failed": 1}
_VALIDATION_RANKS = {"passed": 4, "partial": 3, "not_run": 2, "failed": 1}
_SCOPE_RANKS = {"clean": 2, "violated": 1}
_AUTHORITY_RANKS = {"authorized": 2, "violation": 1}
_APPROVAL_RANKS = {"approved": 2, "denied": 1}
_BUDGET_RANKS = {"within_budget": 2, "exceeded": 1}
_COVERAGE_RANKS = {"evaluated": 1}
_BUDGET_EXCEEDED_STATUSES = frozenset(
    {"exceeded", "exceed", "over_limit", "overlimit", "exhausted", "breached"}
)


def _transition(baseline: str, current: str, ranks: dict[str, int]) -> GovernanceTransition:
    if "unknown" in {baseline, current}:
        return GovernanceTransition.UNKNOWN
    if baseline == current:
        return GovernanceTransition.UNCHANGED
    baseline_rank = ranks.get(baseline)
    current_rank = ranks.get(current)
    if baseline_rank is None or current_rank is None or baseline_rank == current_rank:
        return GovernanceTransition.INCOMPARABLE
    if current_rank > baseline_rank:
        return GovernanceTransition.IMPROVED
    return GovernanceTransition.REGRESSED


def _record_state(
    records: list[ApprovalRecord] | list[AuthorityRecord], coverage: CoverageState
) -> str:
    if coverage != CoverageState.EVALUATED:
        return coverage.value
    states = sorted({record.state.value for record in records})
    if len(states) == 1:
        return states[0]
    return "unknown" if not states else "mixed"


def _budget_state(record: BudgetRecord) -> str:
    status = record.status.strip().lower()
    if status in _BUDGET_EXCEEDED_STATUSES or (
        record.limit is not None
        and record.consumed is not None
        and record.consumed > record.limit
    ):
        return "exceeded"
    if status in {"", "unknown"}:
        return "unknown"
    return "within_budget"


def _budget_fact(projection: ExecutionProjection) -> str:
    coverage = projection.governance_coverage.budget
    if coverage != CoverageState.EVALUATED:
        return coverage.value
    states = sorted({_budget_state(record) for record in projection.budget_records})
    if len(states) == 1:
        return states[0]
    return "unknown" if not states else "mixed"


def _facts(projection: ExecutionProjection) -> dict[GovernanceDimension, str]:
    coverage = projection.governance_coverage
    return {
        GovernanceDimension.NATIVE_OUTCOME: derive_native_outcome(
            projection.lifecycle, projection.decisions
        ).value,
        GovernanceDimension.GOVERNED_OUTCOME: projection.outcome.value,
        GovernanceDimension.VALIDATION: projection.validation.value,
        GovernanceDimension.SCOPE: projection.scope.value,
        GovernanceDimension.AUTHORITY: _record_state(
            projection.authority_records, coverage.authority
        ),
        GovernanceDimension.APPROVAL: _record_state(
            projection.approval_records, coverage.approval
        ),
        GovernanceDimension.BUDGET: _budget_fact(projection),
        GovernanceDimension.AUTHORITY_COVERAGE: coverage.authority.value,
        GovernanceDimension.APPROVAL_COVERAGE: coverage.approval.value,
        GovernanceDimension.BUDGET_COVERAGE: coverage.budget.value,
        GovernanceDimension.VALIDATION_COVERAGE: coverage.validation.value,
        GovernanceDimension.SCOPE_COVERAGE: coverage.scope.value,
    }


def _ranks_for(dimension: GovernanceDimension) -> dict[str, int]:
    if dimension in {
        GovernanceDimension.NATIVE_OUTCOME,
        GovernanceDimension.GOVERNED_OUTCOME,
    }:
        return _OUTCOME_RANKS
    if dimension == GovernanceDimension.VALIDATION:
        return _VALIDATION_RANKS
    if dimension == GovernanceDimension.SCOPE:
        return _SCOPE_RANKS
    if dimension == GovernanceDimension.AUTHORITY:
        return _AUTHORITY_RANKS
    if dimension == GovernanceDimension.APPROVAL:
        return _APPROVAL_RANKS
    if dimension == GovernanceDimension.BUDGET:
        return _BUDGET_RANKS
    return _COVERAGE_RANKS


def compare_governance_projections(
    baseline: ExecutionProjection, current: ExecutionProjection
) -> GovernanceRegressionDelta:
    """Compare governance facts without using a projection's producer identity."""
    baseline_facts = _facts(baseline)
    current_facts = _facts(current)
    dimensions = [
        GovernanceDimensionDelta(
            dimension=dimension,
            baseline=baseline_facts[dimension],
            current=current_facts[dimension],
            transition=_transition(
                baseline_facts[dimension], current_facts[dimension], _ranks_for(dimension)
            ),
        )
        for dimension in _DIMENSION_ORDER
    ]
    return GovernanceRegressionDelta(
        baseline_run_id=baseline.run_id,
        current_run_id=current.run_id,
        dimensions=dimensions,
    )
# NOTE: This module is source-neutral by construction: no ranking or transition
# selection reads a projection's source/run identity. Source- and run-id-neutral
# transitions are locked by tests/test_regression.py.
