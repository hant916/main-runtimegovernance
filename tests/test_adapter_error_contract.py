"""Tests for adapter error propagation contract.

Runtime decision errors and tool execution errors must have stable,
deterministic, and tested behavior.
"""
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from ailuros import AilurosRuntime
from ailuros.adapters import (
    AdapterContext,
    LocalCallableAdapter,
)
from ailuros.errors import AilurosNotFoundError
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


# --- Runtime decision failure prevents tool execution ---

def test_before_tool_call_exception_prevents_execution():
    """Runtime decision error must prevent tool execution."""
    runtime = MagicMock()
    runtime.before_tool_call.side_effect = RuntimeError("connection lost")
    adapter = LocalCallableAdapter(runtime)
    context = AdapterContext(run_id="run-1", tool_name="test.tool", arguments={})
    called = False

    def fn():
        nonlocal called
        called = True

    with pytest.raises(RuntimeError, match="connection lost"):
        adapter.execute_tool(fn, context)

    assert not called


def test_before_tool_call_storage_error_prevents_execution():
    """Storage error in runtime decision must prevent execution."""
    runtime = MagicMock()
    runtime.before_tool_call.side_effect = RuntimeError("db unavailable")
    adapter = LocalCallableAdapter(runtime)
    context = AdapterContext(run_id="run-2", tool_name="data.read", arguments={})
    called = False

    def fn():
        nonlocal called
        called = True

    with pytest.raises(RuntimeError, match="db unavailable"):
        adapter.execute_tool(fn, context)

    assert not called


# --- Tool execution failure is visible to caller ---

def test_adapter_tool_exception_propagates():
    """Tool execution failure must propagate to the caller via adapter."""
    decision = _make_decision(GovernanceDecisionType.ALLOW)
    runtime = _make_runtime(decision)
    adapter = LocalCallableAdapter(runtime)
    context = AdapterContext(run_id="run-10", tool_name="fail.test", arguments={})

    def failing_fn():
        raise ValueError("tool failure")

    with pytest.raises(ValueError, match="tool failure"):
        adapter.execute_tool(failing_fn, context)

    runtime.record_tool_result.assert_not_called()


def test_wrapped_tool_error_captured_in_result(tmp_path):
    """wrap_tool must capture tool errors without re-raising."""
    runtime = AilurosRuntime(storage_path=tmp_path / "runtime.sqlite")
    run = runtime.start_run("test")

    def fail():
        raise ValueError("exploded")

    result = runtime.wrap_tool("explode", fail)(run_id=run.run_id)

    assert not result.blocked
    assert result.error is not None
    assert "ValueError" in result.error
    assert "exploded" in result.error
    assert result.result is None


# --- Error propagation through wrap_tool ---

def test_before_tool_call_failure_in_wrap_tool(tmp_path):
    """wrap_tool must propagate before_tool_call failures."""
    runtime = AilurosRuntime(storage_path=tmp_path / "runtime.sqlite")
    called = False

    def fn():
        nonlocal called
        called = True

    with pytest.raises(AilurosNotFoundError):
        runtime.wrap_tool("test", fn)(run_id="nonexistent-run")

    assert not called
