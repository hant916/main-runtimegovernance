import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from ailuros.adapters import (
    AdapterContext,
    AdapterDecisionStatus,
    LocalCallableAdapter,
    ToolAdapter,
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
        created_at=datetime.now(tz=timezone.utc),  # noqa: UP017
    )


def _make_runtime(decision: GovernanceDecision) -> MagicMock:
    runtime = MagicMock()
    runtime.before_tool_call.return_value = decision
    return runtime


def test_adapter_no_framework_imports():
    framework_names = ["langchain", "llamaindex", "autogen", "crewai"]
    for name in framework_names:
        assert name not in sys.modules, f"{name} should not be imported"


def test_adapter_allowed_returns_result():
    decision = _make_decision(GovernanceDecisionType.ALLOW)
    runtime = _make_runtime(decision)

    def add(x: int, y: int) -> int:
        return x + y

    adapter = LocalCallableAdapter(runtime)
    context = AdapterContext(run_id="run-1", tool_name="math.add", arguments={"x": 1, "y": 2})
    result = adapter.execute_tool(add, context)

    assert result.status == AdapterDecisionStatus.ALLOWED
    assert result.result == 3
    assert result.decision.allowed
    runtime.before_tool_call.assert_called_once_with(
        run_id="run-1",
        tool_name="math.add",
        arguments={"x": 1, "y": 2},
        metadata={},
    )


def test_adapter_blocked_does_not_execute():
    decision = _make_decision(GovernanceDecisionType.BLOCK, reason="Blocked by policy.")
    runtime = _make_runtime(decision)
    called = False

    def dangerous() -> None:
        nonlocal called
        called = True

    adapter = LocalCallableAdapter(runtime)
    context = AdapterContext(run_id="run-2", tool_name="danger.run", arguments={})
    result = adapter.execute_tool(dangerous, context)

    assert result.status == AdapterDecisionStatus.BLOCKED
    assert not result.decision.allowed
    assert result.decision.decision == GovernanceDecisionType.BLOCK
    assert not called


def test_adapter_require_review_does_not_execute():
    decision = _make_decision(GovernanceDecisionType.REQUIRE_REVIEW, reason="Requires review.")
    runtime = _make_runtime(decision)
    called = False

    def suspicious() -> None:
        nonlocal called
        called = True

    adapter = LocalCallableAdapter(runtime)
    context = AdapterContext(run_id="run-3", tool_name="suspicious.action", arguments={})
    result = adapter.execute_tool(suspicious, context)

    assert result.status == AdapterDecisionStatus.REQUIRES_REVIEW
    assert not result.decision.allowed
    assert result.decision.decision == GovernanceDecisionType.REQUIRE_REVIEW
    assert not called


def test_adapter_is_protocol():
    decision = _make_decision(GovernanceDecisionType.ALLOW)
    runtime = _make_runtime(decision)
    assert isinstance(LocalCallableAdapter(runtime), ToolAdapter)


def test_adapter_context_forbids_extra():
    with pytest.raises(ValueError):
        AdapterContext(run_id="x", tool_name="t", unknown_field="boom")
