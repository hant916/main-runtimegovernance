from examples.refund_agent.main import run_demo
from ailuros.storage import SQLiteStorage


def test_refund_demo_blocks_payment_refund(tmp_path):
    db = tmp_path / "demo.sqlite"
    run_id, refund_called = run_demo(db)
    events = SQLiteStorage(db).list_events(run_id)

    assert not refund_called
    assert any(event.event_type.value == "tool_call_blocked" for event in events)
    assert not any(
        event.event_type.value == "tool_result_received"
        and event.payload.get("tool_name") == "payment.issue_refund"
        for event in events
    )
