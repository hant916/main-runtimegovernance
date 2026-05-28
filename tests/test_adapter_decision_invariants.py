import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

from ailuros.adapters import (
    AdapterContext,
    AdapterDecisionStatus,
    LocalCallableAdapter,
)
from ailuros.models import GovernanceDecision, GovernanceDecisionType


def _make_decision(
    decision_type: GovernanceDecisionType,
    reason: str = "No matching policy.",
) -> GovernanceDecision:
    return GovernanceDecision(
        decision_id=str(uuid.uuid4()),
        run_id="test-run",
        decision=decision_type,
        allowed=decision_type == GovernanceDecisionType.ALLOW,
        reason=reason,
        created_at=datetime.now(tz=UTC),
    )


def _make_runtime(decision: GovernanceDecision) -> MagicMock:
    runtime = MagicMock()
    runtime.before_tool_call.return_value = decision
    return runtime


def test_allow_executes_tool_exactly_once():
    decision = _make_decision(GovernanceDecisionType.ALLOW)
    runtime = _make_runtime(decision)
    fn = MagicMock(return_value=42)

    adapter = LocalCallableAdapter(runtime)
    context = AdapterContext(
        run_id="inv-run-1",
        tool_name="test.allow_fn",
        arguments={"x": 1},
    )
    result = adapter.execute_tool(fn, context)

    assert result.status == AdapterDecisionStatus.ALLOWED
    fn.assert_called_once_with(x=1)
    assert result.result == 42


def test_block_never_executes_tool():
    decision = _make_decision(GovernanceDecisionType.BLOCK, reason="Blocked.")
    runtime = _make_runtime(decision)
    fn = MagicMock()

    adapter = LocalCallableAdapter(runtime)
    context = AdapterContext(
        run_id="inv-run-2",
        tool_name="test.block_fn",
        arguments={},
    )
    result = adapter.execute_tool(fn, context)

    assert result.status == AdapterDecisionStatus.BLOCKED
    fn.assert_not_called()


def test_review_never_executes_tool():
    decision = _make_decision(
        GovernanceDecisionType.REQUIRE_REVIEW, reason="Review needed."
    )
    runtime = _make_runtime(decision)
    fn = MagicMock()

    adapter = LocalCallableAdapter(runtime)
    context = AdapterContext(
        run_id="inv-run-3",
        tool_name="test.review_fn",
        arguments={},
    )
    result = adapter.execute_tool(fn, context)

    assert result.status == AdapterDecisionStatus.REQUIRES_REVIEW
    fn.assert_not_called()


def test_before_tool_call_invoked_before_tool_execution():
    decision = _make_decision(GovernanceDecisionType.ALLOW)
    call_order: list[str] = []

    runtime = MagicMock()
    runtime.before_tool_call.side_effect = lambda *args, **kwargs: (
        call_order.append("before_tool_call"),
        decision,
    )[-1]

    fn = MagicMock()
    fn.side_effect = lambda **kwargs: (call_order.append("fn"), "done")[-1]

    adapter = LocalCallableAdapter(runtime)
    context = AdapterContext(
        run_id="inv-run-4",
        tool_name="test.order_fn",
        arguments={"x": 1},
    )
    adapter.execute_tool(fn, context)

    assert call_order == ["before_tool_call", "fn"]
