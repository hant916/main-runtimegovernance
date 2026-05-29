from __future__ import annotations

from ailuros import AilurosRuntime, GovernanceDecisionType, RuntimeEventType
from ailuros.audit import build_audit_report, build_audit_summary, build_run_summary
from ailuros.replay import ReplayService


def test_minimal_dogfood_governance_demo(tmp_path):
    runtime = AilurosRuntime(storage_path=tmp_path / "governance.sqlite")

    run = runtime.start_run({"task": "read config file"})
    decision = runtime.before_tool_call(
        run.run_id,
        "filesystem.read_file",
        {"path": "/etc/config.yaml"},
    )
    runtime.after_tool_call(
        run.run_id,
        "filesystem.read_file",
        {"path": "/etc/config.yaml"},
        result={"content": "key: value"},
    )
    runtime.complete_run(run.run_id, output="config loaded")

    actual_run = runtime.storage.get_run(run.run_id)
    events = runtime.list_events(run.run_id)

    # 1. Decision is recorded with governance fields
    assert decision.decision is GovernanceDecisionType.ALLOW
    assert decision.allowed
    assert decision.run_id == run.run_id
    assert decision.reason == "No matching policy."
    assert decision.decision_id.startswith("dec_")

    # 2. Events are ordered with monotonic sequence numbers
    assert len(events) >= 6
    sequences = [e.sequence for e in events if e.sequence is not None]
    assert sequences == list(range(1, len(sequences) + 1))
    event_types = [e.event_type for e in events]
    assert RuntimeEventType.RUN_STARTED in event_types
    assert RuntimeEventType.USER_INPUT_RECEIVED in event_types
    assert RuntimeEventType.TOOL_CALL_REQUESTED in event_types
    assert RuntimeEventType.POLICY_EVALUATION_RESULT in event_types
    assert RuntimeEventType.GOVERNANCE_DECISION in event_types
    assert RuntimeEventType.TOOL_CALL_EXECUTED in event_types
    assert RuntimeEventType.TOOL_RESULT_RECEIVED in event_types
    assert RuntimeEventType.OUTPUT_GENERATED in event_types
    assert RuntimeEventType.RUN_COMPLETED in event_types

    # 3. Run summary is produced from storage
    run_summary = build_run_summary(runtime.storage, run.run_id)
    assert run_summary.run_id == run.run_id
    assert run_summary.status == actual_run.status.value
    assert run_summary.event_count == len(events)
    assert run_summary.decision_counts.get("allow", 0) >= 1

    # 4. Replay timeline is reconstructable from stored events
    replay = ReplayService(runtime.storage)
    timeline = replay.build_timeline(run.run_id)
    assert len(timeline) == len(events)
    for i, entry in enumerate(timeline):
        assert entry["sequence_number"] == events[i].sequence
        assert entry["event_type"] == events[i].event_type.value
        assert entry["event_id"] == events[i].event_id

    # 5. Audit summary is generated from event evidence
    audit_summary = build_audit_summary(events)
    assert audit_summary.decision == "allow"
    assert audit_summary.reason == "No matching policy."
    assert audit_summary.tool == "filesystem.read_file"

    # 6. Audit report connects summary + events into structured output
    audit_report = build_audit_report(run_summary, events)
    assert audit_report["metadata_version"] == "1"
    assert audit_report["run_id"] == run.run_id
    assert audit_report["status"] == run_summary.status
    assert audit_report["counts"]["event_count"] == len(events)
    assert len(audit_report["timeline"]) == len(events)

    # All five outputs reference the same run_id
    for artifact, rid in [
        ("decision", decision.run_id),
        ("events", events[0].run_id),
        ("run_summary", run_summary.run_id),
        ("timeline", str(run.run_id)),
        ("audit_report", audit_report["run_id"]),
    ]:
        assert rid == run.run_id, f"{artifact} run_id mismatch: {rid} != {run.run_id}"
