from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict

from ailuros.models import Environment, Policy, PolicyOperator
from ailuros.policy.operators import OperatorResult, evaluate_operator
from ailuros.utils import get_by_path


class ToolCallContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    environment: Environment
    tool_name: str
    arguments: dict[str, Any] = {}
    metadata: dict[str, Any] = {}
    prior_events: list[dict[str, Any]] = []


@dataclass(frozen=True)
class MatchDetails:
    matched: bool
    failed_conditions: list[str]


class PolicyMatcher:
    def matches(self, policy: Policy, context: ToolCallContext) -> bool:
        return self.match_details(policy, context).matched

    def match_details(self, policy: Policy, context: ToolCallContext) -> MatchDetails:
        failed = []
        context_data = context.model_dump(mode="json")
        for source in (policy.scope, policy.match):
            for field, condition in source.items():
                actual = get_by_path(context_data, field)
                result = self._evaluate_condition(actual, condition)
                if not result.matched:
                    failed.append(f"{field}: {result.reason or 'condition failed'}")
        if policy.requires_previous_steps:
            for field, condition in policy.requires_previous_steps.items():
                actual = get_by_path(context_data, field)
                result = self._evaluate_condition(actual, condition)
                if not result.matched:
                    failed.append(
                        f"requires_previous_steps.{field}: {result.reason or 'condition failed'}"
                    )
        return MatchDetails(matched=not failed, failed_conditions=failed)

    def _evaluate_condition(self, actual: Any, condition: Any) -> OperatorResult:
        if isinstance(condition, dict):
            for operator_value, expected in condition.items():
                result = evaluate_operator(PolicyOperator(operator_value), actual, expected)
                if not result.matched:
                    return result
            return OperatorResult(True)
        return evaluate_operator(PolicyOperator.EQ, actual, condition)
