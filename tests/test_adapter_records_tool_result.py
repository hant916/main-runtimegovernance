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


def test_allowed_records_tool_result():
    decision = _make_decision(GovernanceDecisionType.ALLOW)
    runtime = _make_runtime(decision)

    fn = MagicMock(return_value=42)

    adapter = LocalCallableAdapter(runtime)
    context = AdapterContext(
        run_id="rec-run-1",
        tool_name="test.succeed",
        arguments={"x": 1, "y": 2},
    )
    result = adapter.execute_tool(fn, context)

    assert result.status == AdapterDecisionStatus.ALLOWED
    assert result.result == 42
    runtime.record_tool_result.assert_called_once_with(
        run_id="rec-run-1",
        tool_name="test.succeed",
        result=42,
        arguments={"x": 1, "y": 2},
    )


def test_blocked_does_not_record_tool_result():
    decision = _make_decision(GovernanceDecisionType.BLOCK, reason="Blocked.")
    runtime = _make_runtime(decision)

    adapter = LocalCallableAdapter(runtime)
    context = AdapterContext(
        run_id="rec-run-2",
        tool_name="test.blocked",
        arguments={},
    )
    result = adapter.execute_tool(MagicMock(), context)

    assert result.status == AdapterDecisionStatus.BLOCKED
    runtime.record_tool_result.assert_not_called()


def test_require_review_does_not_record_tool_result():
    decision = _make_decision(
        GovernanceDecisionType.REQUIRE_REVIEW, reason="Review needed."
    )
    runtime = _make_runtime(decision)

    adapter = LocalCallableAdapter(runtime)
    context = AdapterContext(
        run_id="rec-run-3",
        tool_name="test.review",
        arguments={},
    )
    result = adapter.execute_tool(MagicMock(), context)

    assert result.status == AdapterDecisionStatus.REQUIRES_REVIEW
    runtime.record_tool_result.assert_not_called()


def test_record_tool_result_after_execution():
    decision = _make_decision(GovernanceDecisionType.ALLOW)
    runtime = _make_runtime(decision)

    call_order: list[str] = []
    fn = MagicMock()
    fn.side_effect = lambda **kwargs: call_order.append("fn")

    runtime.record_tool_result.side_effect = (
        lambda *args, **kwargs: call_order.append("record_tool_result")
    )

    adapter = LocalCallableAdapter(runtime)
    context = AdapterContext(
        run_id="rec-run-4",
        tool_name="test.order",
        arguments={},
    )
    adapter.execute_tool(fn, context)

    assert call_order == ["fn", "record_tool_result"]
