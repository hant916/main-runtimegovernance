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


def test_requires_previous_steps_absent_is_backward_compatible():
    policy = Policy(
        policy_id="test.absent",
        version="1",
        severity=Severity.LOW,
        match={"tool_name": "test_tool"},
    )
    context = ToolCallContext(environment="development", tool_name="test_tool")
    assert PolicyMatcher().matches(policy, context)


def test_requires_previous_steps_empty_is_backward_compatible():
    policy = Policy(
        policy_id="test.empty",
        version="1",
        severity=Severity.LOW,
        requires_previous_steps={},
        match={"tool_name": "test_tool"},
    )
    context = ToolCallContext(environment="development", tool_name="test_tool")
    assert PolicyMatcher().matches(policy, context)


def test_requires_previous_steps_met():
    policy = Policy(
        policy_id="test.met",
        version="1",
        severity=Severity.LOW,
        match={"tool_name": "test_tool"},
        requires_previous_steps={"prior_events.0.event_type": {"eq": "run_started"}},
    )
    prior_events = [
        {"event_type": "run_started", "payload": {"input": "hello"}},
    ]
    context = ToolCallContext(
        environment="development",
        tool_name="test_tool",
        prior_events=prior_events,
    )
    assert PolicyMatcher().matches(policy, context)


def test_requires_previous_steps_unmet():
    policy = Policy(
        policy_id="test.unmet",
        version="1",
        severity=Severity.LOW,
        match={"tool_name": "test_tool"},
        requires_previous_steps={"prior_events.0.event_type": {"eq": "tool_call_executed"}},
    )
    context = ToolCallContext(
        environment="development",
        tool_name="test_tool",
        prior_events=[{"event_type": "run_started"}],
    )
    assert not PolicyMatcher().matches(policy, context)


def test_requires_previous_steps_empty_prior_events():
    policy = Policy(
        policy_id="test.empty_events",
        version="1",
        severity=Severity.LOW,
        match={"tool_name": "test_tool"},
        requires_previous_steps={"prior_events.0": {"exists": None}},
    )
    context = ToolCallContext(
        environment="development",
        tool_name="test_tool",
        prior_events=[],
    )
    assert not PolicyMatcher().matches(policy, context)


def test_requires_previous_steps_multiple_conditions_all_met():
    policy = Policy(
        policy_id="test.multiple_met",
        version="1",
        severity=Severity.LOW,
        match={"tool_name": "test_tool"},
        requires_previous_steps={
            "prior_events.0.event_type": {"eq": "run_started"},
            "prior_events.1.event_type": {"eq": "tool_call_requested"},
        },
    )
    prior_events = [
        {"event_type": "run_started", "payload": {"input": "hello"}},
        {"event_type": "tool_call_requested", "payload": {"tool_name": "get_balance"}},
    ]
    context = ToolCallContext(
        environment="development",
        tool_name="test_tool",
        prior_events=prior_events,
    )
    assert PolicyMatcher().matches(policy, context)


def test_requires_previous_steps_partial_failure():
    policy = Policy(
        policy_id="test.partial",
        version="1",
        severity=Severity.LOW,
        match={"tool_name": "test_tool"},
        requires_previous_steps={
            "prior_events.0.event_type": {"eq": "run_started"},
            "prior_events.1.event_type": {"eq": "tool_call_requested"},
        },
    )
    prior_events = [
        {"event_type": "run_started", "payload": {"input": "hello"}},
        {"event_type": "tool_call_executed", "payload": {"tool_name": "get_balance"}},
    ]
    context = ToolCallContext(
        environment="development",
        tool_name="test_tool",
        prior_events=prior_events,
    )
    details = PolicyMatcher().match_details(policy, context)
    assert not details.matched
    assert any("requires_previous_steps" in fc for fc in details.failed_conditions)
