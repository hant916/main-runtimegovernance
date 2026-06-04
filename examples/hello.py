from __future__ import annotations

import tempfile
from pathlib import Path

from ailuros import AilurosRuntime
from ailuros.audit import build_audit_summary, build_run_summary
from ailuros.path import ExpectedPath
from ailuros.replay import ReplayService


def main() -> None:
    tmp_dir = Path(tempfile.mkdtemp())
    runtime = AilurosRuntime(storage_path=tmp_dir / "hello.sqlite")
    run = runtime.start_run({"task": "hello governance"})
    decision = runtime.before_tool_call(run.run_id, "demo.greet", {"name": "world"})
    runtime.after_tool_call(run.run_id, "demo.greet", {"name": "world"}, result={"greeting": "hello world"})
    runtime.validate_path(
        run.run_id,
        ExpectedPath(path_id="greet", required_tool_calls=["demo.greet"]),
    )
    runtime.complete_run(run.run_id, output="done")
    events = runtime.list_events(run.run_id)

    print("=== Decision ===")
    print(f"  decision_id: {decision.decision_id}")
    print(f"  decision:    {decision.decision.value}")
    print(f"  allowed:     {decision.allowed}")
    print(f"  reason:      {decision.reason}")
    print(f"  tool:        {decision.tool_name}")
    print()

    print("=== Ordered Events ===")
    for e in events:
        print(f"  #{e.sequence} {e.event_type.value}  {e.event_id}")
    print()

    print("=== Run Summary ===")
    summary = build_run_summary(runtime.storage, run.run_id)
    print(f"  run_id:       {summary.run_id}")
    print(f"  status:       {summary.status}")
    print(f"  events:       {summary.event_count}")
    print(f"  decisions:    {summary.decision_counts}")
    print()

    print("=== Replay Timeline ===")
    replay = ReplayService(runtime.storage)
    timeline = replay.build_timeline(run.run_id)
    for entry in timeline:
        print(f"  #{entry['sequence_number']} {entry['event_type']}  {entry['event_id']}")
    print()

    print("=== Audit Summary ===")
    audit = build_audit_summary(events)
    print(f"  decision:         {audit.decision}")
    print(f"  reason:           {audit.reason}")
    print(f"  tool:             {audit.tool}")
    print(f"  path_validation:  {audit.path_validation}")
    print()

    print("Hello governance demo complete.")

    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
