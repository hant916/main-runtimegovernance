from ailuros import GovernanceDecisionType, Policy, Severity
from ailuros.policy import DecisionResolver


def test_decision_resolver_priority_severity_and_policy_id():
    policies = [
        Policy(
            policy_id="z.warn",
            version="1",
            decision=GovernanceDecisionType.WARN,
            severity=Severity.CRITICAL,
            match={"tool_name": "x"},
        ),
        Policy(
            policy_id="b.review",
            version="1",
            decision=GovernanceDecisionType.REQUIRE_REVIEW,
            severity=Severity.MEDIUM,
            match={"tool_name": "x"},
        ),
        Policy(
            policy_id="a.review",
            version="1",
            decision=GovernanceDecisionType.REQUIRE_REVIEW,
            severity=Severity.HIGH,
            match={"tool_name": "x"},
        ),
    ]

    decision = DecisionResolver().resolve("run_1", policies)

    assert decision.decision is GovernanceDecisionType.REQUIRE_REVIEW
    assert decision.severity is Severity.HIGH
    assert not decision.allowed


def test_decision_resolver_no_match_allows():
    decision = DecisionResolver().resolve("run_1", [])

    assert decision.decision is GovernanceDecisionType.ALLOW
    assert decision.allowed
