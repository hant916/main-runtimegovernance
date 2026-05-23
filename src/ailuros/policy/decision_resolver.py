import uuid
from datetime import UTC, datetime

from ailuros.models import GovernanceDecision, GovernanceDecisionType, Policy, Severity


class DecisionResolver:
    decision_priority = {
        GovernanceDecisionType.BLOCK: 0,
        GovernanceDecisionType.REQUIRE_REVIEW: 1,
        GovernanceDecisionType.SANITIZE: 2,
        GovernanceDecisionType.WARN: 3,
        GovernanceDecisionType.ALLOW: 4,
    }
    severity_priority = {
        Severity.CRITICAL: 0,
        Severity.HIGH: 1,
        Severity.MEDIUM: 2,
        Severity.LOW: 3,
    }

    def resolve(self, run_id: str, policies: list[Policy]) -> GovernanceDecision:
        if not policies:
            return GovernanceDecision(
                decision_id=new_decision_id(),
                run_id=run_id,
                decision=GovernanceDecisionType.ALLOW,
                allowed=True,
                reason="No matching policy.",
                severity=Severity.LOW,
                created_at=datetime.now(UTC),
            )
        winner = sorted(
            policies,
            key=lambda policy: (
                self.decision_priority[policy.decision],
                self.severity_priority[policy.severity],
                policy.policy_id,
            ),
        )[0]
        allowed = winner.decision in {GovernanceDecisionType.ALLOW, GovernanceDecisionType.WARN}
        return GovernanceDecision(
            decision_id=new_decision_id(),
            run_id=run_id,
            decision=winner.decision,
            allowed=allowed,
            reason=winner.reason or f"Matched policy {winner.policy_id}.",
            severity=winner.severity,
            matched_policy_ids=sorted(policy.policy_id for policy in policies),
            created_at=datetime.now(UTC),
        )


def new_decision_id() -> str:
    return f"dec_{uuid.uuid4().hex}"
