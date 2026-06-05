from __future__ import annotations

import json
from pathlib import Path

from ailuros.regression import RegressionService


def _load_fixture(name: str) -> list[dict]:
    path = Path(__file__).resolve().parent.parent / "examples" / "evaluation" / name
    return json.loads(path.read_text(encoding="utf-8"))


def _record(
    event_id: str,
    event_type: str,
    sequence: int,
    evidence: dict | None = None,
) -> dict:
    return {
        "event_id": event_id,
        "run_id": "test-run",
        "event_type": event_type,
        "timestamp": "2026-06-05T00:00:00+00:00",
        "sequence": sequence,
        "evidence": evidence or {},
    }


class TestEvidenceRegressionGeneric:
    def test_no_change_identical_timelines(self):
        baseline = [
            _record("a", "evidence", 1, {"version": "1.0", "event_type": "nav"}),
            _record("b", "evidence", 2, {"version": "1.0", "event_type": "int"}),
        ]
        current = [
            _record("a2", "evidence", 1, {"version": "1.0", "event_type": "nav"}),
            _record("b2", "evidence", 2, {"version": "1.0", "event_type": "int"}),
        ]
        result = RegressionService().compare_evidence_timeline(baseline, current)
        assert result.passed is True
        assert result.baseline_count == 2
        assert result.current_count == 2
        assert result.diffs == []

    def test_no_change_from_fixture_files(self):
        baseline = _load_fixture("evidence-regression-baseline.json")
        current = _load_fixture("evidence-regression-current.json")
        result = RegressionService().compare_evidence_timeline(baseline, current)
        assert result.passed is True
        assert result.diffs == []

    def test_missing_evidence_detected(self):
        baseline = [
            _record("a", "evidence", 1, {"version": "1.0", "event_type": "nav"}),
            _record("b", "evidence", 2, {"version": "1.0", "event_type": "int"}),
        ]
        current = [
            _record("a2", "evidence", 1, {"version": "1.0", "event_type": "nav"}),
        ]
        result = RegressionService().compare_evidence_timeline(baseline, current)
        assert result.passed is False
        assert len(result.diffs) == 1
        assert result.diffs[0].kind == "missing_evidence"
        assert result.diffs[0].index == 1
        assert result.baseline_count == 2
        assert result.current_count == 1

    def test_added_evidence_detected(self):
        baseline = [
            _record("a", "evidence", 1, {"version": "1.0", "event_type": "nav"}),
        ]
        current = [
            _record("a2", "evidence", 1, {"version": "1.0", "event_type": "nav"}),
            _record("b2", "evidence", 2, {"version": "1.0", "event_type": "int"}),
        ]
        result = RegressionService().compare_evidence_timeline(baseline, current)
        assert result.passed is False
        assert len(result.diffs) == 1
        assert result.diffs[0].kind == "added_evidence"
        assert result.diffs[0].index == 1
        assert result.baseline_count == 1
        assert result.current_count == 2

    def test_changed_sequence_reported(self):
        baseline = [
            _record("a", "evidence", 1, {"version": "1.0", "event_type": "nav"}),
        ]
        current = [
            _record("a2", "evidence", 99, {"version": "1.0", "event_type": "nav"}),
        ]
        result = RegressionService().compare_evidence_timeline(baseline, current)
        assert result.passed is False
        assert len(result.diffs) == 1
        assert result.diffs[0].kind == "changed_evidence"
        assert "sequence" in result.diffs[0].message

    def test_changed_evidence_version_reported(self):
        baseline = [
            _record("a", "evidence", 1, {"version": "1.0", "event_type": "nav"}),
        ]
        current = [
            _record("a2", "evidence", 1, {"version": "2.0", "event_type": "nav"}),
        ]
        result = RegressionService().compare_evidence_timeline(baseline, current)
        assert result.passed is False
        assert len(result.diffs) == 1
        assert result.diffs[0].kind == "changed_evidence"
        assert "evidence_version" in result.diffs[0].message

    def test_changed_event_type_reported(self):
        baseline = [
            _record("a", "evidence", 1, {"version": "1.0", "event_type": "nav"}),
        ]
        current = [
            _record("a2", "external_evidence", 1, {"version": "1.0", "event_type": "nav"}),
        ]
        result = RegressionService().compare_evidence_timeline(baseline, current)
        assert result.passed is False
        assert len(result.diffs) == 1
        assert result.diffs[0].kind == "changed_evidence"
        assert "event_type" in result.diffs[0].message

    def test_changed_evidence_event_type_reported(self):
        baseline = [
            _record("a", "evidence", 1, {"version": "1.0", "event_type": "nav"}),
        ]
        current = [
            _record("a2", "evidence", 1, {"version": "1.0", "event_type": "page_view"}),
        ]
        result = RegressionService().compare_evidence_timeline(baseline, current)
        assert result.passed is False
        assert len(result.diffs) == 1
        assert result.diffs[0].kind == "changed_evidence"
        assert "evidence_event_type" in result.diffs[0].message


class TestEvidenceRegressionPayloadPaths:
    def test_payload_path_opt_in_reports_diff(self):
        baseline = [
            _record("a", "evidence", 1, {
                "version": "1.0", "event_type": "nav", "action": "click"
            }),
        ]
        current = [
            _record("a2", "evidence", 1, {
                "version": "1.0", "event_type": "nav", "action": "hover"
            }),
        ]
        result = RegressionService().compare_evidence_timeline(
            baseline, current, payload_paths=["action"]
        )
        assert result.passed is False
        assert len(result.diffs) == 1
        assert result.diffs[0].kind == "changed_evidence"
        assert "payload.action" in result.diffs[0].message

    def test_payload_path_no_diff_when_identical(self):
        baseline = [
            _record("a", "evidence", 1, {
                "version": "1.0", "event_type": "nav", "action": "click"
            }),
        ]
        current = [
            _record("a2", "evidence", 1, {
                "version": "1.0", "event_type": "nav", "action": "click"
            }),
        ]
        result = RegressionService().compare_evidence_timeline(
            baseline, current, payload_paths=["action"]
        )
        assert result.passed is True
        assert result.diffs == []

    def test_payload_path_not_compared_by_default(self):
        baseline = [
            _record("a", "evidence", 1, {
                "version": "1.0", "event_type": "nav", "action": "click"
            }),
        ]
        current = [
            _record("a2", "evidence", 1, {
                "version": "1.0", "event_type": "nav", "action": "hover"
            }),
        ]
        result = RegressionService().compare_evidence_timeline(baseline, current)
        assert result.passed is True
        assert result.diffs == []

    def test_nested_payload_path(self):
        baseline = [
            _record("a", "evidence", 1, {
                "version": "1.0", "event_type": "nav",
                "metadata": {"category": "nav", "priority": "high"},
            }),
        ]
        current = [
            _record("a2", "evidence", 1, {
                "version": "1.0", "event_type": "nav",
                "metadata": {"category": "nav", "priority": "low"},
            }),
        ]
        result = RegressionService().compare_evidence_timeline(
            baseline, current, payload_paths=["metadata.priority"]
        )
        assert result.passed is False
        assert len(result.diffs) == 1
        assert "payload.metadata.priority" in result.diffs[0].message

    def test_payload_path_missing_in_baseline(self):
        baseline = [
            _record("a", "evidence", 1, {
                "version": "1.0", "event_type": "nav",
            }),
        ]
        current = [
            _record("a2", "evidence", 1, {
                "version": "1.0", "event_type": "nav",
                "action": "click",
            }),
        ]
        result = RegressionService().compare_evidence_timeline(
            baseline, current, payload_paths=["action"]
        )
        assert result.passed is False
        assert "MISSING_IN_BASELINE" in result.diffs[0].message

    def test_payload_path_missing_in_current(self):
        baseline = [
            _record("a", "evidence", 1, {
                "version": "1.0", "event_type": "nav",
                "action": "click",
            }),
        ]
        current = [
            _record("a2", "evidence", 1, {
                "version": "1.0", "event_type": "nav",
            }),
        ]
        result = RegressionService().compare_evidence_timeline(
            baseline, current, payload_paths=["action"]
        )
        assert result.passed is False
        assert "MISSING_IN_CURRENT" in result.diffs[0].message


class TestEvidenceRegressionDeterminism:
    def test_same_inputs_produce_same_output(self):
        recs = [
            _record("a", "evidence", 1, {"version": "1.0", "event_type": "nav"}),
            _record("b", "evidence", 2, {"version": "1.0", "event_type": "int"}),
        ]
        r1 = RegressionService().compare_evidence_timeline(recs, recs)
        r2 = RegressionService().compare_evidence_timeline(recs, recs)
        assert r1.passed == r2.passed
        assert r1.baseline_count == r2.baseline_count
        assert r1.current_count == r2.current_count
        assert len(r1.diffs) == len(r2.diffs)
