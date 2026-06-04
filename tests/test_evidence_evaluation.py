from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from ailuros.evaluation import (
    EvaluationCase,
    EvaluationCaseLoadError,
    EvaluationService,
    EvidenceEventExpectation,
    load_evaluation_cases,
)
from ailuros.models import RuntimeEvent, RuntimeEventType

EVIDENCE_GOLDEN_FILE = (
    Path(__file__).parent.parent / "examples" / "evaluation" / "evidence_golden.json"
)


def event(
    sequence: int,
    event_type: RuntimeEventType,
    payload: dict[str, object] | None = None,
) -> RuntimeEvent:
    return RuntimeEvent(
        event_id=f"evt_{sequence}",
        run_id="run_1",
        event_type=event_type,
        timestamp=datetime.now(UTC),
        payload=payload or {},
        sequence=sequence,
    )


def _matching_evidence_events(
    expectations: list[object],
) -> list[RuntimeEvent]:
    events: list[RuntimeEvent] = []
    seq = 1
    for exp in expectations:
        if isinstance(exp, EvidenceEventExpectation):
            payload: dict[str, object] = {}
            if exp.evidence_event_type is not None:
                payload["event_type"] = exp.evidence_event_type
            if exp.version is not None:
                payload["version"] = exp.version
            if exp.payload_contains is not None:
                payload.update(exp.payload_contains)
            events.append(event(seq, RuntimeEventType.EVIDENCE, payload))
            seq += 1
    return events


class TestEvidenceEventExpectation:
    def test_passes_with_matching_evidence(self):
        events = [
            event(1, RuntimeEventType.RUN_STARTED),
            event(
                2,
                RuntimeEventType.EVIDENCE,
                {
                    "version": "1.0.0",
                    "event_type": "example.event",
                    "data": {"key": "value"},
                },
            ),
        ]
        case = EvaluationCase(
            id="case_1",
            name="case",
            expectations=[
                EvidenceEventExpectation(
                    evidence_event_type="example.event",
                    version="1.0.0",
                )
            ],
        )
        result = EvaluationService().evaluate(events, [case])[0]

        assert result.passed is True
        assert result.failures == []
        assert len(result.evidence) >= 1
        assert result.evidence[0].expectation_type == "evidence_event"

    def test_fails_when_no_evidence_events(self):
        events = [
            event(1, RuntimeEventType.RUN_STARTED),
            event(2, RuntimeEventType.GOVERNANCE_DECISION, {"decision": "allow"}),
        ]
        case = EvaluationCase(
            id="case_1",
            name="case",
            expectations=[EvidenceEventExpectation(evidence_event_type="example.event")],
        )
        result = EvaluationService().evaluate(events, [case])[0]

        assert result.passed is False
        assert "Expected evidence event" in result.failures[0].message
        assert "actual=missing" in result.failures[0].message

    def test_fails_when_version_mismatch(self):
        events = [
            event(
                1,
                RuntimeEventType.EVIDENCE,
                {"version": "1.0.0", "event_type": "example.event"},
            ),
        ]
        case = EvaluationCase(
            id="case_1",
            name="case",
            expectations=[
                EvidenceEventExpectation(
                    evidence_event_type="example.event",
                    version="2.0.0",
                )
            ],
        )
        result = EvaluationService().evaluate(events, [case])[0]

        assert result.passed is False
        assert "Expected evidence event" in result.failures[0].message

    def test_fails_when_event_type_mismatch(self):
        events = [
            event(
                1,
                RuntimeEventType.EVIDENCE,
                {"version": "1.0.0", "event_type": "other.event"},
            ),
        ]
        case = EvaluationCase(
            id="case_1",
            name="case",
            expectations=[
                EvidenceEventExpectation(evidence_event_type="example.event")
            ],
        )
        result = EvaluationService().evaluate(events, [case])[0]

        assert result.passed is False

    def test_passes_with_payload_contains_match(self):
        events = [
            event(
                1,
                RuntimeEventType.EVIDENCE,
                {
                    "version": "1.0.0",
                    "event_type": "example.event",
                    "action": "click",
                    "target": "button",
                },
            ),
        ]
        case = EvaluationCase(
            id="case_1",
            name="case",
            expectations=[
                EvidenceEventExpectation(
                    evidence_event_type="example.event",
                    payload_contains={"action": "click"},
                )
            ],
        )
        result = EvaluationService().evaluate(events, [case])[0]

        assert result.passed is True

    def test_fails_when_payload_contains_mismatch(self):
        events = [
            event(
                1,
                RuntimeEventType.EVIDENCE,
                {
                    "version": "1.0.0",
                    "event_type": "example.event",
                    "action": "click",
                },
            ),
        ]
        case = EvaluationCase(
            id="case_1",
            name="case",
            expectations=[
                EvidenceEventExpectation(
                    evidence_event_type="example.event",
                    payload_contains={"action": "hover"},
                )
            ],
        )
        result = EvaluationService().evaluate(events, [case])[0]

        assert result.passed is False
        assert "Expected evidence event" in result.failures[0].message

    def test_matches_external_evidence_events(self):
        events = [
            event(
                1,
                RuntimeEventType.EXTERNAL_EVIDENCE,
                {"version": "1.0.0", "event_type": "external.event"},
            ),
        ]
        case = EvaluationCase(
            id="case_1",
            name="case",
            expectations=[
                EvidenceEventExpectation(evidence_event_type="external.event"),
            ],
        )
        result = EvaluationService().evaluate(events, [case])[0]

        assert result.passed is True


class TestEvidenceGoldenCaseLoading:
    def test_loads_all_cases(self):
        cases = load_evaluation_cases(EVIDENCE_GOLDEN_FILE)
        assert len(cases) == 5
        assert all(c.id for c in cases)
        assert all(c.name for c in cases)

    def test_loads_non_existent_file(self):
        with pytest.raises(EvaluationCaseLoadError, match="could not read evaluation case file"):
            load_evaluation_cases("/non/existent/path.json")

    def test_golden_cases_are_application_neutral(self):
        cases = load_evaluation_cases(EVIDENCE_GOLDEN_FILE)
        for case in cases:
            for expectation in case.expectations:
                assert isinstance(expectation, EvidenceEventExpectation)
                if expectation.evidence_event_type:
                    domain = expectation.evidence_event_type.lower()
                    assert "browser" not in domain
                    assert "clarify" not in domain
                    assert "dom" not in domain
                    assert "sidepanel" not in domain
                    assert "cta" not in domain


class TestEvidenceGoldenCaseMatching:
    def test_each_passing_case_passes_with_matching_events(self):
        cases = load_evaluation_cases(EVIDENCE_GOLDEN_FILE)
        passing_ids = {"evidence.pass.event_found", "evidence.pass.payload_contains"}

        for case in cases:
            if case.id not in passing_ids:
                continue
            events = _matching_evidence_events(case.expectations)
            result = EvaluationService().evaluate(events, [case])[0]

            assert result.passed, (
                f"Golden case '{case.id}' should pass with matching events:\n"
                f"  failures: {[f.message for f in result.failures]}"
            )
            assert result.case_id == case.id

    def test_each_failing_case_fails_without_matching_events(self):
        cases = load_evaluation_cases(EVIDENCE_GOLDEN_FILE)
        failing_ids = {
            "evidence.fail.no_events",
            "evidence.fail.wrong_version",
            "evidence.fail.payload_contains_mismatch",
        }

        for case in cases:
            if case.id not in failing_ids:
                continue
            result = EvaluationService().evaluate([], [case])[0]

            assert not result.passed, (
                f"Golden case '{case.id}' should fail with no events:\n"
                f"  failures: {[f.message for f in result.failures]}"
            )
            assert result.case_id == case.id

    def test_wrong_version_case_fails_with_correct_version_event(self):
        cases = load_evaluation_cases(EVIDENCE_GOLDEN_FILE)
        case = next(c for c in cases if c.id == "evidence.fail.wrong_version")

        events = [
            event(
                1,
                RuntimeEventType.EVIDENCE,
                {"version": "1.0.0", "event_type": "example.event"},
            ),
        ]
        result = EvaluationService().evaluate(events, [case])[0]

        assert not result.passed

    def test_payload_contains_mismatch_case_fails_with_wrong_payload(self):
        cases = load_evaluation_cases(EVIDENCE_GOLDEN_FILE)
        case = next(c for c in cases if c.id == "evidence.fail.payload_contains_mismatch")

        events = [
            event(
                1,
                RuntimeEventType.EVIDENCE,
                {"version": "1.0.0", "event_type": "example.event", "action": "click"},
            ),
        ]
        result = EvaluationService().evaluate(events, [case])[0]

        assert not result.passed

    def test_passing_case_fails_when_evidence_type_wrong(self):
        cases = load_evaluation_cases(EVIDENCE_GOLDEN_FILE)
        case = next(c for c in cases if c.id == "evidence.pass.event_found")

        events = [
            event(
                1,
                RuntimeEventType.EVIDENCE,
                {"version": "1.0.0", "event_type": "wrong.event"},
            ),
        ]
        result = EvaluationService().evaluate(events, [case])[0]

        assert not result.passed

    def test_failure_output_identifies_case_and_expected(self):
        cases = load_evaluation_cases(EVIDENCE_GOLDEN_FILE)
        case = next(c for c in cases if c.id == "evidence.fail.no_events")

        result = EvaluationService().evaluate([], [case])[0]

        assert not result.passed
        assert len(result.failures) > 0
        failure_messages = [f.message for f in result.failures]
        combined = " ".join(failure_messages)
        assert "expected evidence event" in combined.lower()


class TestEvidenceEventExpectationModel:
    def test_extra_fields_rejected(self):
        with pytest.raises(ValidationError):
            EvidenceEventExpectation(unknown_field="value")

    def test_invalid_case_structure_rejected(self, tmp_path: Path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text(
            json.dumps(
                [
                    {
                        "id": "case",
                        "name": "case",
                        "expectations": [
                            {"type": "evidence_event", "unknown_field": "x"}
                        ],
                    }
                ]
            ),
            encoding="utf-8",
        )
        with pytest.raises(EvaluationCaseLoadError, match="invalid evaluation case file"):
            load_evaluation_cases(bad_file)
