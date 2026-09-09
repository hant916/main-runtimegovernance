from dataclasses import dataclass

from ailuros.models import Policy
from ailuros.policy.matcher import ActorSubstitutionContext, PolicyMatcher, ToolCallContext


@dataclass(frozen=True)
class PolicyEvaluation:
    matched_policies: list[Policy]
    evaluated_policy_count: int
    matched_policy_count: int


class PolicyEngine:
    def __init__(self, policies: list[Policy]) -> None:
        self.policies = policies
        self.matcher = PolicyMatcher()

    def evaluate_tool_call(self, context: ToolCallContext) -> PolicyEvaluation:
        return self._evaluate(context)

    def evaluate_actor_substitution(
        self, context: ActorSubstitutionContext
    ) -> PolicyEvaluation:
        return self._evaluate(context)

    def _evaluate(
        self, context: ToolCallContext | ActorSubstitutionContext
    ) -> PolicyEvaluation:
        active = [policy for policy in self.policies if policy.enabled]
        matched = [policy for policy in active if self.matcher.matches(policy, context)]
        return PolicyEvaluation(
            matched_policies=matched,
            evaluated_policy_count=len(active),
            matched_policy_count=len(matched),
        )
