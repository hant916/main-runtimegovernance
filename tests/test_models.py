from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ailuros import (
    Environment,
    Policy,
    Run,
    RunStatus,
    RuntimeEvent,
    RuntimeEventType,
    Severity,
)


def test_runtime_event_type_contains_canonical_events():
    values = {event.value for event in RuntimeEventType}

    assert "run_started" in values
    assert "payload_redacted" in values
    assert len(values) == 24


def test_models_serialize_to_json():
    run = Run(
        run_id="run_1",
        agent_id="agent",
        environment=Environment.DEVELOPMENT,
        status=RunStatus.RUNNING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    event = RuntimeEvent(
        event_id="evt_1",
        run_id=run.run_id,
        event_type=RuntimeEventType.RUN_STARTED,
        timestamp=datetime.now(UTC),
        payload={"ok": True},
    )

    assert "run_1" in run.model_dump_json()
    assert "run_started" in event.model_dump_json()


def test_invalid_enum_is_rejected():
    with pytest.raises(ValidationError):
        RuntimeEvent(
            event_id="evt_1",
            run_id="run_1",
            event_type="unknown",
            timestamp=datetime.now(UTC),
        )


def test_policy_accepts_valid_json_definition():
    policy = Policy(
        policy_id="refund.high",
        version="1",
        decision="require_review",
        severity=Severity.HIGH,
        match={"tool_name": "payment.issue_refund", "arguments.amount_eur": {"gt": 500}},
    )

    assert policy.match["arguments.amount_eur"]["gt"] == 500
