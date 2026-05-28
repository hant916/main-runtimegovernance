from __future__ import annotations

import json
from datetime import UTC, datetime

from typer.testing import CliRunner

from ailuros.cli import app
from ailuros.models import RuntimeEvent, RuntimeEventType
from ailuros.regression.timeline import replay_timeline


def make_event(
    event_id: str,
    run_id: str,
    event_type: RuntimeEventType,
    payload: dict | None = None,
) -> RuntimeEvent:
    return RuntimeEvent(
        event_id=event_id,
        run_id=run_id,
        event_type=event_type,
        timestamp=datetime.now(UTC),
        payload=payload or {},
    )


def make_decision_event(
    event_id: str,
    run_id: str,
    decision: str,
    allowed: bool,
) -> RuntimeEvent:
    return make_event(
        event_id=event_id,
        run_id=run_id,
        event_type=RuntimeEventType.GOVERNANCE_DECISION,
        payload={"decision": decision, "allowed": allowed, "reason": "test"},
    )


def _dump(events: list[RuntimeEvent]) -> str:
    return json.dumps([e.model_dump(mode="json") for e in events])


class TestReplayTimelineUnit:
    def test_all_decisions_pass(self, tmp_path):
        tl = tmp_path / "timeline.json"
        tl.write_text(
            _dump([
                make_decision_event("e1", "run-1", "allow", True),
                make_decision_event("e2", "run-1", "block", False),
                make_decision_event("e3", "run-1", "warn", True),
            ]),
            encoding="utf-8",
        )
        result = replay_timeline(tl)
        assert result.total_cases == 3
        assert result.passed_cases == 3
        assert result.failed_cases == 0
        assert result.passed is True

    def test_inconsistent_decision_fails(self, tmp_path):
        tl = tmp_path / "timeline.json"
        tl.write_text(
            _dump([
                make_decision_event("e1", "run-1", "block", True),
            ]),
            encoding="utf-8",
        )
        result = replay_timeline(tl)
        assert result.total_cases == 1
        assert result.passed_cases == 0
        assert result.failed_cases == 1
        assert result.passed is False
        assert len(result.failures) == 1
        assert "block" in result.failures[0]
        assert "allowed=True" in result.failures[0]

    def test_unknown_decision_type_fails(self, tmp_path):
        tl = tmp_path / "timeline.json"
        tl.write_text(
            _dump([
                make_decision_event("e1", "run-1", "invalid_decision", True),
            ]),
            encoding="utf-8",
        )
        result = replay_timeline(tl)
        assert result.total_cases == 1
        assert result.failed_cases == 1
        assert result.passed is False
        assert "unknown decision type" in result.failures[0]

    def test_missing_file_fails(self, tmp_path):
        tl = tmp_path / "nonexistent.json"
        result = replay_timeline(tl)
        assert result.total_cases == 0
        assert result.failed_cases == 0
        assert result.passed is False
        assert len(result.failures) == 1
        assert "not found" in result.failures[0]

    def test_invalid_json_fails(self, tmp_path):
        tl = tmp_path / "bad.json"
        tl.write_text("not json", encoding="utf-8")
        result = replay_timeline(tl)
        assert result.total_cases == 0
        assert result.failed_cases == 0
        assert result.passed is False
        assert len(result.failures) == 1
        assert "invalid timeline file" in result.failures[0]

    def test_not_a_list_fails(self, tmp_path):
        tl = tmp_path / "bad.json"
        tl.write_text('{"not": "a list"}', encoding="utf-8")
        result = replay_timeline(tl)
        assert result.total_cases == 0
        assert result.failed_cases == 0
        assert result.passed is False
        assert len(result.failures) == 1
        assert "must be a JSON array" in result.failures[0]

    def test_empty_timeline_has_zero_cases(self, tmp_path):
        tl = tmp_path / "empty.json"
        tl.write_text("[]", encoding="utf-8")
        result = replay_timeline(tl)
        assert result.total_cases == 0
        assert result.passed_cases == 0
        assert result.failed_cases == 0
        assert result.passed is True

    def test_mixed_pass_fail(self, tmp_path):
        tl = tmp_path / "mixed.json"
        tl.write_text(
            _dump([
                make_decision_event("e1", "run-1", "allow", True),
                make_decision_event("e2", "run-1", "block", True),
                make_decision_event("e3", "run-1", "warn", True),
            ]),
            encoding="utf-8",
        )
        result = replay_timeline(tl)
        assert result.total_cases == 3
        assert result.passed_cases == 2
        assert result.failed_cases == 1
        assert result.passed is False

    def test_sanitize_requires_allowed_true(self, tmp_path):
        tl = tmp_path / "sanitize.json"
        tl.write_text(
            _dump([
                make_decision_event("e1", "run-1", "sanitize", True),
            ]),
            encoding="utf-8",
        )
        result = replay_timeline(tl)
        assert result.total_cases == 1
        assert result.passed_cases == 1
        assert result.passed is True

    def test_require_review_requires_allowed_false(self, tmp_path):
        tl = tmp_path / "review.json"
        tl.write_text(
            _dump([
                make_decision_event("e1", "run-1", "require_review", False),
            ]),
            encoding="utf-8",
        )
        result = replay_timeline(tl)
        assert result.total_cases == 1
        assert result.passed_cases == 1
        assert result.passed is True

    def test_non_decision_events_are_ignored(self, tmp_path):
        tl = tmp_path / "mixed_events.json"
        tl.write_text(
            _dump([
                make_event("e1", "run-1", RuntimeEventType.RUN_STARTED),
                make_decision_event("e2", "run-1", "allow", True),
                make_event("e3", "run-1", RuntimeEventType.RUN_COMPLETED),
            ]),
            encoding="utf-8",
        )
        result = replay_timeline(tl)
        assert result.total_cases == 1
        assert result.passed_cases == 1
        assert result.failed_cases == 0


class TestReplayTimelineCLI:
    def test_pass_replay_exits_zero(self, tmp_path):
        tl = tmp_path / "pass.json"
        tl.write_text(
            _dump([make_decision_event("e1", "run-1", "allow", True)]),
            encoding="utf-8",
        )
        result = CliRunner().invoke(app, ["regression", "replay", str(tl)])
        assert result.exit_code == 0
        assert "1 case(s)" in result.output
        assert "1 passed" in result.output

    def test_fail_replay_exits_nonzero(self, tmp_path):
        tl = tmp_path / "fail.json"
        tl.write_text(
            _dump([make_decision_event("e1", "run-1", "block", True)]),
            encoding="utf-8",
        )
        result = CliRunner().invoke(app, ["regression", "replay", str(tl)])
        assert result.exit_code == 1
        assert "FAIL" in result.output
        assert "1 case(s)" in result.output
        assert "1 failed" in result.output

    def test_invalid_timeline_exits_nonzero(self, tmp_path):
        tl = tmp_path / "bad.json"
        tl.write_text("not json", encoding="utf-8")
        result = CliRunner().invoke(app, ["regression", "replay", str(tl)])
        assert result.exit_code == 1
        assert "invalid timeline file" in result.output

    def test_missing_timeline_exits_nonzero(self, tmp_path):
        tl = tmp_path / "nonexistent.json"
        result = CliRunner().invoke(app, ["regression", "replay", str(tl)])
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_summary_includes_counts(self, tmp_path):
        tl = tmp_path / "summary.json"
        tl.write_text(
            _dump([
                make_decision_event("e1", "run-1", "allow", True),
                make_decision_event("e2", "run-1", "block", False),
            ]),
            encoding="utf-8",
        )
        result = CliRunner().invoke(app, ["regression", "replay", str(tl)])
        assert result.exit_code == 0
        assert "2 case(s)" in result.output
        assert "2 passed" in result.output
        assert "0 failed" in result.output
