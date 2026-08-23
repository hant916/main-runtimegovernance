"""Adapter conformance harness.

Framework-neutral validation of the ToolAdapter contract using local doubles only.
No concrete MCP, LangChain, CrewAI, or other third-party adapters are implemented.

The harness validates:
  - Call shape: execute_tool(fn, context) -> AdapterResult
  - Result shape: status, decision, reason, result fields with correct types
  - Error mapping: runtime decision failures block execution; tool errors propagate
  - Audit metadata: context fields preserved; metadata round-tripped
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from ailuros.adapters import (
    AdapterContext,
    AdapterDecisionStatus,
    AdapterResult,
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
        created_at=datetime.now(tz=UTC),
    )


def _make_runtime(decision: GovernanceDecision) -> MagicMock:
    runtime = MagicMock()
    runtime.before_tool_call.return_value = decision
    return runtime


class _FakeToolAdapter:
    """Local double that satisfies the ToolAdapter protocol for harness validation.

    A future MCP/LangChain/CrewAI adapter must implement the same interface.
    """

    def execute_tool(
        self,
        fn: Callable[..., Any],
        context: AdapterContext,
    ) -> AdapterResult:
        """Minimal conformant implementation using a null governance check."""
        decision = _make_decision(GovernanceDecisionType.ALLOW, reason="fake adapter")
        if context.tool_name == "__harness_blocked__":
            decision = _make_decision(GovernanceDecisionType.BLOCK, reason="blocked by harness")
            return AdapterResult(
                status=AdapterDecisionStatus.BLOCKED,
                decision=decision,
                reason=decision.reason,
            )
        result = fn(**context.arguments)
        return AdapterResult(
            status=AdapterDecisionStatus.ALLOWED,
            decision=decision,
            reason=decision.reason,
            result=result,
        )


# --- Call shape conformance ---

def _assert_result_shape(result: AdapterResult) -> None:
    """Structural contract every AdapterResult must satisfy regardless of backend."""
    assert isinstance(result, AdapterResult)
    assert isinstance(result.status, AdapterDecisionStatus)
    assert isinstance(result.decision, GovernanceDecision)
    assert isinstance(result.reason, str)


def test_protocol_instance_check():
    """LocalCallableAdapter and any future adapter must pass isinstance(ToolAdapter)."""
    runtime = _make_runtime(_make_decision(GovernanceDecisionType.ALLOW))
    assert isinstance(LocalCallableAdapter(runtime), ToolAdapter)


def test_local_double_satisfies_protocol():
    """A local double implementing the ToolAdapter interface must pass protocol check."""
    fake = _FakeToolAdapter()
    assert isinstance(fake, ToolAdapter)


def test_call_shape_conformance():
    """execute_tool(fn, context) -> AdapterResult with correct typing."""
    fake = _FakeToolAdapter()
    context = AdapterContext(run_id="r1", tool_name="test.inc", arguments={"x": 1})
    result = fake.execute_tool(lambda x: x + 1, context)
    _assert_result_shape(result)
    assert result.status == AdapterDecisionStatus.ALLOWED
    assert result.result == 2


def test_local_callable_adapter_call_shape():
    """LocalCallableAdapter must also satisfy the call shape contract."""
    runtime = _make_runtime(_make_decision(GovernanceDecisionType.ALLOW))
    adapter = LocalCallableAdapter(runtime)
    context = AdapterContext(run_id="r2", tool_name="test.add", arguments={"a": 3, "b": 4})
    result = adapter.execute_tool(lambda a, b: a + b, context)
    _assert_result_shape(result)


# --- Result shape conformance ---

def test_result_status_values():
    """AdapterResult.status must be one of the three AdapterDecisionStatus values."""
    assert set(AdapterDecisionStatus) == {"allowed", "blocked", "requires_review"}


def test_result_null_result_on_blocked():
    """Blocked decisions must carry result=None (no tool execution happened)."""
    fake = _FakeToolAdapter()
    context = AdapterContext(run_id="r3", tool_name="__harness_blocked__", arguments={})
    result = fake.execute_tool(lambda: "should not run", context)
    _assert_result_shape(result)
    assert result.status == AdapterDecisionStatus.BLOCKED
    assert result.result is None


def test_result_must_contain_decision_reference():
    """Every AdapterResult must carry the governance decision that produced it."""
    runtime = _make_runtime(_make_decision(GovernanceDecisionType.BLOCK, reason="no"))
    adapter = LocalCallableAdapter(runtime)
    context = AdapterContext(run_id="r4", tool_name="test.noop", arguments={})
    result = adapter.execute_tool(lambda: None, context)
    assert result.decision.decision == GovernanceDecisionType.BLOCK
    assert result.decision.allowed is False


# --- Error mapping conformance ---

def test_runtime_failure_prevents_tool_execution():
    """Any adapter must prevent tool execution when runtime governance raises."""
    runtime = MagicMock()
    runtime.before_tool_call.side_effect = RuntimeError("governance unavailable")
    adapter = LocalCallableAdapter(runtime)
    context = AdapterContext(run_id="r5", tool_name="test.unsafe", arguments={})
    called = False

    def unsafe_fn():
        nonlocal called
        called = True

    with pytest.raises(RuntimeError, match="governance unavailable"):
        adapter.execute_tool(unsafe_fn, context)
    assert not called


def test_tool_error_propagates_from_adapter():
    """Tool execution errors must propagate; adapter must not silently swallow them."""
    runtime = _make_runtime(_make_decision(GovernanceDecisionType.ALLOW))
    adapter = LocalCallableAdapter(runtime)
    context = AdapterContext(run_id="r6", tool_name="test.fail", arguments={})

    def bomb():
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        adapter.execute_tool(bomb, context)


def test_error_does_not_record_result():
    """When tool execution fails, the adapter must not record a result."""
    runtime = _make_runtime(_make_decision(GovernanceDecisionType.ALLOW))
    adapter = LocalCallableAdapter(runtime)
    context = AdapterContext(run_id="r7", tool_name="test.fail", arguments={})

    def bomb():
        raise TypeError("bad type")

    with pytest.raises(TypeError, match="bad type"):
        adapter.execute_tool(bomb, context)
    runtime.record_tool_result.assert_not_called()


# --- Audit metadata conformance ---

def test_metadata_round_trip():
    """Adapter must pass metadata through to the runtime via before_tool_call."""
    decision = _make_decision(GovernanceDecisionType.ALLOW)
    runtime = _make_runtime(decision)
    adapter = LocalCallableAdapter(runtime)
    meta = {"session_id": "abc123", "user": "test-user"}
    context = AdapterContext(
        run_id="r8",
        tool_name="test.meta",
        arguments={"key": "val"},
        metadata=meta,
    )
    result = adapter.execute_tool(lambda key: key.upper(), context)
    assert result.result == "VAL"
    runtime.before_tool_call.assert_called_once_with(
        run_id="r8",
        tool_name="test.meta",
        arguments={"key": "val"},
        metadata=meta,
    )


def test_context_extra_fields_forbidden():
    """AdapterContext must reject unknown fields (strict schema)."""
    with pytest.raises(ValueError):
        AdapterContext(run_id="x", tool_name="t", extra="should-fail")


def test_context_defaults_preserved():
    """AdapterContext defaults (arguments={}, metadata={}) must not be None."""
    ctx = AdapterContext(run_id="r9", tool_name="t.def")
    assert ctx.arguments == {}
    assert ctx.metadata == {}


def test_execute_tool_passes_all_arguments():
    """All arguments in context.arguments must reach the tool function."""
    runtime = _make_runtime(_make_decision(GovernanceDecisionType.ALLOW))
    adapter = LocalCallableAdapter(runtime)
    fn = MagicMock(return_value="ok")
    context = AdapterContext(
        run_id="r10", tool_name="test.kwargs", arguments={"a": 1, "b": 2}
    )
    adapter.execute_tool(fn, context)
    fn.assert_called_once_with(a=1, b=2)


def test_adapter_accept_label_does_not_create_governance_facts():
    """A producer-native ALLOWED accept label must not itself be treated as an
    authority authorization, approval, or clean-state governance fact: the
    adapter only echoes the decision it was given and manufactures no such state."""
    runtime = _make_runtime(
        _make_decision(GovernanceDecisionType.ALLOW, reason="adapter non-inference check")
    )
    adapter = LocalCallableAdapter(runtime)
    context = AdapterContext(run_id="r-accept", tool_name="test.accept", arguments={})
    result = adapter.execute_tool(lambda: "ok", context)

    assert result.status == AdapterDecisionStatus.ALLOWED
    assert result.decision.decision == GovernanceDecisionType.ALLOW
    dumped = result.model_dump(mode="json")
    assert set(dumped) == {"status", "decision", "reason", "result"}
    assert "authorized" not in dumped
    assert "approved" not in dumped
    assert "clean" not in dumped
