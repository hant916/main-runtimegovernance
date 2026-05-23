from __future__ import annotations

from pathlib import Path
from typing import Any

from ailuros import AilurosRuntime, Environment, RunStatus
from ailuros.path import ExpectedPath

REFUND_WAS_CALLED = False


def get_order_status(order_id: str) -> dict[str, Any]:
    return {"order_id": order_id, "status": "delivered", "amount_eur": 780}


def issue_refund(order_id: str, amount_eur: int, reason: str) -> dict[str, Any]:
    global REFUND_WAS_CALLED
    REFUND_WAS_CALLED = True
    return {"order_id": order_id, "amount_eur": amount_eur, "reason": reason, "refunded": True}


def run_demo(storage_path: str | Path = "ailuros.sqlite") -> tuple[str, bool]:
    global REFUND_WAS_CALLED
    REFUND_WAS_CALLED = False
    policy_path = Path(__file__).with_name("policies").joinpath("refund.json")
    runtime = AilurosRuntime(
        agent_id="refund_demo_agent",
        environment=Environment.DEVELOPMENT,
        storage_path=storage_path,
        policies=[policy_path],
    )
    run = runtime.start_run("I want a refund for order ORD-9231.")
    order = get_order_status("ORD-9231")
    runtime.record_tool_result(run.run_id, "order.get_status", order, {"order_id": "ORD-9231"})
    refund = runtime.wrap_tool("payment.issue_refund", issue_refund)
    result = refund(
        run_id=run.run_id,
        order_id="ORD-9231",
        amount_eur=order["amount_eur"],
        reason="customer_request",
    )
    runtime.validate_path(
        run.run_id,
        ExpectedPath(
            path_id="refund_review",
            required_tool_calls=["payment.issue_refund"],
        ),
    )
    if result.blocked:
        runtime.complete_run(
            run.run_id,
            output={"decision": result.decision.decision.value, "reason": result.decision.reason},
            status=RunStatus.REQUIRES_REVIEW,
        )
    else:
        runtime.complete_run(run.run_id, output=result.result)
    print(f"run_id={run.run_id}")
    print(f"decision={result.decision.decision.value}")
    print(f"reason={result.decision.reason}")
    return run.run_id, REFUND_WAS_CALLED


if __name__ == "__main__":
    run_demo()
