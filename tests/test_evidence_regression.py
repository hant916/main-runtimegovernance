from __future__ import annotations

import pytest
from pydantic import ValidationError

from ailuros.regression import (
    EvidenceTimelineDiff,
    EvidenceTimelineRegressionResult,
    RegressionService,
)


def _evidence_record(
    sequence: int = 1,
    event_type: str = "evidence",
    version: str = "1.0.0",
    evt_type: str = "example.event",
    payload: dict | None = None,
) -> dict:
    return {
        "event_id": f"evt_{sequence}",
        "run_id": "run_test",
        "event_type": event_type,
        "timestamp": "2024-01-01T00:00:00+00:00",
        "sequence": sequence,
        "evidence": {
            "version": version,
            "event_type": evt_type,
            "payload": payload or {"action": "click"},
        },
    }


class TestEvidenceTimelineDiffModel:
    def test_extra_fields_rejected(self):
        with pytest.raises(ValidationError):
            EvidenceTimelineDiff.model_validate(
                {"index": 0, "kind": "test", "message": "msg", "extra": "bad"}
            )


class TestEvidenceTimelineRegressionResultModel:
    def test_extra_fields_rejected(self):
        with pytest.raises(ValidationError):
            EvidenceTimelineRegressionResult.model_validate(
                {
                    "passed": True,
                    "baseline_count": 1,
                    "current_count": 1,
                    "diffs": [],
                    "extra": "bad",
                }
            )


class TestEvidenceTimelineNoRegression:
    def test_identical_timelines_pass(self):
        baseline = [
            _evidence_record(1, evt_type="nav"),
            _evidence_record(2, evt_type="click"),
        ]
        current = [
            _evidence_record(1, evt_type="nav"),
            _evidence_record(2, evt_type="click"),
        ]

        result = RegressionService().compare_evidence_timeline(baseline, current)

        assert result.passed is True
        assert result.diffs == []
        assert result.baseline_count == 2
        assert result.current_count == 2

    def test_empty_timelines_pass(self):
        result = RegressionService().compare_evidence_timeline([], [])

        assert result.passed is True
        assert result.diffs == []
        assert result.baseline_count == 0
        assert result.current_count == 0

    def test_single_event_pass(self):
        baseline = [_evidence_record(1)]
        current = [_evidence_record(1)]

        result = RegressionService().compare_evidence_timeline(baseline, current)

        assert result.passed is True


class TestEvidenceTimelineMissingEvidence:
    def test_fewer_events_in_current_is_regression(self):
        baseline = [
            _evidence_record(1, evt_type="nav"),
            _evidence_record(2, evt_type="click"),
            _evidence_record(3, evt_type="submit"),
        ]
        current = [
            _evidence_record(1, evt_type="nav"),
        ]

        result = RegressionService().compare_evidence_timeline(baseline, current)

        assert result.passed is False
        assert result.baseline_count == 3
        assert result.current_count == 1
        assert len(result.diffs) >= 2
        kinds = {d.kind for d in result.diffs}
        assert "missing_evidence" in kinds

    def test_current_is_empty_is_regression(self):
        baseline = [_evidence_record(1)]
        current: list[dict] = []

        result = RegressionService().compare_evidence_timeline(baseline, current)

        assert result.passed is False
        assert len(result.diffs) == 1
        assert result.diffs[0].kind == "missing_evidence"
        assert result.diffs[0].index == 0


class TestEvidenceTimelineAddedEvidence:
    def test_more_events_in_current_is_regression(self):
        baseline = [_evidence_record(1, evt_type="nav")]
        current = [
            _evidence_record(1, evt_type="nav"),
            _evidence_record(2, evt_type="click"),
            _evidence_record(3, evt_type="submit"),
        ]

        result = RegressionService().compare_evidence_timeline(baseline, current)

        assert result.passed is False
        assert result.baseline_count == 1
        assert result.current_count == 3
        kinds = {d.kind for d in result.diffs}
        assert "added_evidence" in kinds

    def test_baseline_empty_current_has_events_is_regression(self):
        baseline: list[dict] = []
        current = [_evidence_record(1)]

        result = RegressionService().compare_evidence_timeline(baseline, current)

        assert result.passed is False
        assert len(result.diffs) == 1
        assert result.diffs[0].kind == "added_evidence"


class TestEvidenceTimelineChangedStableField:
    def test_version_changed_is_regression(self):
        baseline = [_evidence_record(1, version="1.0.0")]
        current = [_evidence_record(1, version="2.0.0")]

        result = RegressionService().compare_evidence_timeline(baseline, current)

        assert result.passed is False
        assert len(result.diffs) == 1
        assert result.diffs[0].kind == "changed_evidence"
        assert "evidence_version" in result.diffs[0].message

    def test_evidence_event_type_changed_is_regression(self):
        baseline = [_evidence_record(1, evt_type="nav")]
        current = [_evidence_record(1, evt_type="click")]

        result = RegressionService().compare_evidence_timeline(baseline, current)

        assert result.passed is False
        assert len(result.diffs) == 1
        assert result.diffs[0].kind == "changed_evidence"
        assert "evidence_event_type" in result.diffs[0].message

    def test_top_level_event_type_changed_is_regression(self):
        baseline = [_evidence_record(1, event_type="evidence")]
        current = [_evidence_record(1, event_type="external_evidence")]

        result = RegressionService().compare_evidence_timeline(baseline, current)

        assert result.passed is False
        assert len(result.diffs) == 1
        assert result.diffs[0].kind == "changed_evidence"

    def test_sequence_changed_is_regression(self):
        baseline = [_evidence_record(1)]
        current = [_evidence_record(2)]

        result = RegressionService().compare_evidence_timeline(baseline, current)

        assert result.passed is False
        assert len(result.diffs) == 1
        assert result.diffs[0].kind == "changed_evidence"
        assert "sequence" in result.diffs[0].message

    def test_multiple_fields_changed_reports_all(self):
        baseline = [_evidence_record(1, version="1.0.0", evt_type="nav")]
        current = [_evidence_record(1, version="2.0.0", evt_type="click")]

        result = RegressionService().compare_evidence_timeline(baseline, current)

        assert result.passed is False
        assert len(result.diffs) == 1
        assert result.diffs[0].kind == "changed_evidence"
        assert "evidence_version" in result.diffs[0].message
        assert "evidence_event_type" in result.diffs[0].message


class TestEvidenceTimelineOpaquePayload:
    def test_opaque_payload_change_does_not_cause_regression(self):
        baseline = [_evidence_record(1, payload={"action": "click"})]
        current = [_evidence_record(1, payload={"action": "hover"})]

        result = RegressionService().compare_evidence_timeline(baseline, current)

        assert result.passed is True
        assert result.diffs == []

    def test_new_payload_key_does_not_cause_regression(self):
        baseline = [_evidence_record(1, payload={"action": "click"})]
        current = [_evidence_record(1, payload={"action": "click", "extra": "data"})]

        result = RegressionService().compare_evidence_timeline(baseline, current)

        assert result.passed is True

    def test_payload_removed_does_not_cause_regression(self):
        baseline = [_evidence_record(1, payload={"action": "click"})]
        current = [_evidence_record(1, payload={})]

        result = RegressionService().compare_evidence_timeline(baseline, current)

        assert result.passed is True


class TestEvidenceTimelineReordered:
    def test_reordered_events_is_regression(self):
        baseline = [
            _evidence_record(1, evt_type="nav"),
            _evidence_record(2, evt_type="click"),
        ]
        current = [
            _evidence_record(1, evt_type="click"),
            _evidence_record(2, evt_type="nav"),
        ]

        result = RegressionService().compare_evidence_timeline(baseline, current)

        assert result.passed is False


class TestEvidenceTimelineDiffDetails:
    def test_diff_includes_baseline_and_current_records(self):
        baseline = [_evidence_record(1, version="1.0.0")]
        current = [_evidence_record(1, version="2.0.0")]

        result = RegressionService().compare_evidence_timeline(baseline, current)

        diff = result.diffs[0]
        assert diff.baseline_record is not None
        assert diff.baseline_record["evidence"]["version"] == "1.0.0"
        assert diff.current_record is not None
        assert diff.current_record["evidence"]["version"] == "2.0.0"

    def test_missing_diff_has_baseline_record(self):
        baseline = [_evidence_record(1)]
        current: list[dict] = []

        result = RegressionService().compare_evidence_timeline(baseline, current)

        diff = result.diffs[0]
        assert diff.baseline_record is not None
        assert diff.current_record is None

    def test_added_diff_has_current_record(self):
        baseline: list[dict] = []
        current = [_evidence_record(1)]

        result = RegressionService().compare_evidence_timeline(baseline, current)

        diff = result.diffs[0]
        assert diff.baseline_record is None
        assert diff.current_record is not None


class TestEvidenceTimelineExternal:
    def test_external_evidence_type_is_compared(self):
        baseline = [_evidence_record(1, event_type="external_evidence")]
        current = [_evidence_record(1, event_type="external_evidence")]

        result = RegressionService().compare_evidence_timeline(baseline, current)

        assert result.passed is True

    def test_evidence_vs_external_evidence_is_regression(self):
        baseline = [_evidence_record(1, event_type="evidence")]
        current = [_evidence_record(1, event_type="external_evidence")]

        result = RegressionService().compare_evidence_timeline(baseline, current)

        assert result.passed is False
