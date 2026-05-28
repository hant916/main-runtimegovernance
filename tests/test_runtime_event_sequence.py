from ailuros import AilurosRuntime, RuntimeEventType


def test_events_appended_in_sequence_order(tmp_path):
    runtime = AilurosRuntime(storage_path=tmp_path / "seq.sqlite")

    run = runtime.start_run("order test")

    dec = runtime.record_event(
        run.run_id, RuntimeEventType.GOVERNANCE_DECISION, {"decision": "allow"}
    )
    tool = runtime.record_event(
        run.run_id, RuntimeEventType.TOOL_CALL_EXECUTED, {"tool": "calc"}
    )
    runtime.complete_run(run.run_id, output="ok")

    events = runtime.list_events(run.run_id)

    assert len(events) >= 4
    assert events[0].event_type == RuntimeEventType.RUN_STARTED
    assert events[0].sequence == 1
    assert events[1].event_type == RuntimeEventType.USER_INPUT_RECEIVED
    assert events[1].sequence == 2
    assert events[2].event_type == RuntimeEventType.GOVERNANCE_DECISION
    assert events[2].sequence == 3
    assert events[3].event_type == RuntimeEventType.TOOL_CALL_EXECUTED
    assert events[3].sequence == 4

    assert dec.sequence == 3
    assert tool.sequence == 4

    assert all(events[i].sequence < events[i + 1].sequence for i in range(len(events) - 1))


def test_sequence_independent_per_run(tmp_path):
    runtime = AilurosRuntime(storage_path=tmp_path / "indep.sqlite")

    run_a = runtime.start_run("run A")
    run_b = runtime.start_run("run B")

    a1 = runtime.record_event(run_a.run_id, RuntimeEventType.GOVERNANCE_DECISION, {"run": "A"})
    b1 = runtime.record_event(run_b.run_id, RuntimeEventType.GOVERNANCE_DECISION, {"run": "B"})
    a2 = runtime.record_event(run_a.run_id, RuntimeEventType.TOOL_CALL_EXECUTED, {"run": "A"})
    b2 = runtime.record_event(run_b.run_id, RuntimeEventType.TOOL_CALL_EXECUTED, {"run": "B"})

    assert a1.sequence == 3
    assert a2.sequence == 4
    assert b1.sequence == 3
    assert b2.sequence == 4

    events_a = runtime.list_events(run_a.run_id)
    events_b = runtime.list_events(run_b.run_id)

    assert [e.sequence for e in events_a] == [1, 2, 3, 4]
    assert [e.sequence for e in events_b] == [1, 2, 3, 4]


def test_duplicate_sequence_rejected(tmp_path):
    storage_path = tmp_path / "dup.sqlite"
    runtime = AilurosRuntime(storage_path=storage_path)
    run = runtime.start_run("dup test")

    runtime.record_event(run.run_id, RuntimeEventType.GOVERNANCE_DECISION, {"n": 1})

    import sqlite3

    conn = sqlite3.connect(storage_path)
    try:
        cur = conn.execute(
            "SELECT MAX(sequence) FROM events WHERE run_id = ?", (run.run_id,)
        )
        max_seq = cur.fetchone()[0]
        conn.execute(
            "INSERT INTO events"
            "(event_id, run_id, step_id, event_type, timestamp, payload_json, sequence) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "dup_evt",
                run.run_id,
                None,
                "manual_insert",
                "2026-01-01T00:00:00+00:00",
                '{}',
                max_seq,
            ),
        )
        conn.commit()
        raise AssertionError("Expected IntegrityError for duplicate sequence")
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()
