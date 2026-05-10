from copy import deepcopy

from ailuros import Policy, Severity
from ailuros.policy import PolicyMatcher, ToolCallContext


def test_policy_matcher_nested_arguments_and_environment():
    policy = Policy(
        policy_id="refund.high",
        version="1",
        decision="require_review",
        severity=Severity.HIGH,
        scope={"environment": "development"},
        match={"tool_name": "payment.issue_refund", "arguments.amount_eur": {"gt": 500}},
    )
    context = ToolCallContext(
        environment="development",
        tool_name="payment.issue_refund",
        arguments={"amount_eur": 780},
    )

    assert PolicyMatcher().matches(policy, context)


def test_policy_matcher_details_and_no_mutation():
    policy = Policy(
        policy_id="refund.high",
        version="1",
        severity=Severity.HIGH,
        match={"arguments.amount_eur": {"gt": 500}},
    )
    context = ToolCallContext(
        environment="development",
        tool_name="payment.issue_refund",
        arguments={"amount_eur": 100},
    )
    policy_before = deepcopy(policy)
    context_before = deepcopy(context)

    details = PolicyMatcher().match_details(policy, context)

    assert not details.matched
    assert details.failed_conditions
    assert policy == policy_before
    assert context == context_before
