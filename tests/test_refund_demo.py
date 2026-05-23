from ailuros.storage import SQLiteStorage
from examples.refund_agent.main import run_demo


def test_refund_demo_blocks_payment_refund(tmp_path):
    db = tmp_path / "demo.sqlite"
    run_id, refund_called = run_demo(db)
    storage = SQLiteStorage(db)
    run = storage.get_run(run_id)
    events = storage.list_events(run_id)
    event_types = [event.event_type.value for event in events]

    assert not refund_called
    assert run.status.value == "requires_review"
    assert any(
        event.event_type.value == "tool_call_requested"
        and event.payload.get("tool_name") == "payment.issue_refund"
        for event in events
    )
    assert "governance_decision" in event_types
    assert any(event.event_type.value == "tool_call_blocked" for event in events)
    assert "path_validation_result" in event_types
    assert event_types.index("tool_call_blocked") < event_types.index("path_validation_result")
    assert not any(
        event.event_type.value == "tool_result_received"
        and event.payload.get("tool_name") == "payment.issue_refund"
        for event in events
    )
