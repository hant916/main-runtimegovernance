from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ailuros.evaluation import (
    AllowedToolExpectation,
    BlockedToolExpectation,
    EvaluationCaseLoadError,
    EvaluationService,
    GovernanceDecisionExpectation,
    PathValidationExpectation,
    ToolNotExecutedExpectation,
    load_evaluation_cases,
)
from ailuros.evaluation.models import EvaluationExpectation
from ailuros.models import RuntimeEvent, RuntimeEventType

GOLDEN_FILE = Path(__file__).parent.parent / "examples" / "evaluation" / "golden.json"


def event(
    sequence: int,
    event_type: RuntimeEventType,
    payload: dict[str, object] | None = None,
) -> RuntimeEvent:
    return RuntimeEvent(
        event_id=f"evt_{sequence}",
        run_id="golden_test",
        event_type=event_type,
        timestamp=datetime.now(UTC),
        payload=payload or {},
        sequence=sequence,
    )


def _matching_events(expectations: list[EvaluationExpectation]) -> list[RuntimeEvent]:
    events: list[RuntimeEvent] = []
    seq = 1
    for exp in expectations:
        if isinstance(exp, GovernanceDecisionExpectation):
            payload: dict[str, object] = {}
            if exp.decision is not None:
                payload["decision"] = exp.decision
            if exp.allowed is not None:
                payload["allowed"] = exp.allowed
            if exp.severity is not None:
                payload["severity"] = exp.severity
            events.append(event(seq, RuntimeEventType.GOVERNANCE_DECISION, payload))
            seq += 1
        elif isinstance(exp, AllowedToolExpectation):
            events.append(
                event(seq, RuntimeEventType.TOOL_CALL_EXECUTED, {"tool_name": exp.tool_name})
            )
            seq += 1
        elif isinstance(exp, BlockedToolExpectation):
            payload = {"tool_name": exp.tool_name}
            if exp.decision is not None:
                payload["decision"] = exp.decision
            events.append(event(seq, RuntimeEventType.TOOL_CALL_BLOCKED, payload))
            seq += 1
        elif isinstance(exp, ToolNotExecutedExpectation):
            events.append(
                event(
                    seq,
                    RuntimeEventType.TOOL_CALL_BLOCKED,
                    {"tool_name": exp.tool_name, "decision": "block"},
                )
            )
            seq += 1
        elif isinstance(exp, PathValidationExpectation):
            payload = {"path_id": exp.path_id, "valid": exp.valid}
            events.append(event(seq, RuntimeEventType.PATH_VALIDATION_RESULT, payload))
            seq += 1
    return events


class TestGoldenCaseLoading:
    def test_loads_all_cases(self):
        cases = load_evaluation_cases(GOLDEN_FILE)
        assert len(cases) == 8
        assert all(c.id for c in cases)
        assert all(c.name for c in cases)

    def test_loads_non_existent_file(self):
        with pytest.raises(EvaluationCaseLoadError, match="could not read evaluation case file"):
            load_evaluation_cases("/non/existent/path.json")

    def test_loads_malformed_json(self, tmp_path: Path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{not json", encoding="utf-8")
        with pytest.raises(EvaluationCaseLoadError, match="invalid JSON"):
            load_evaluation_cases(bad_file)

    def test_loads_invalid_case_structure(self, tmp_path: Path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text(json.dumps([{"id": "no_name"}]), encoding="utf-8")
        with pytest.raises(EvaluationCaseLoadError, match="invalid evaluation case file"):
            load_evaluation_cases(bad_file)


class TestGoldenCaseDecisionMatching:
    def test_each_golden_case_passes_with_matching_events(self):
        cases = load_evaluation_cases(GOLDEN_FILE)
        assert len(cases) >= 6, "Need at least 6 golden cases"

        for case in cases:
            events = _matching_events(case.expectations)
            result = EvaluationService().evaluate(events, [case])[0]

            assert result.passed, (
                f"Golden case '{case.id}' should pass with matching events:\n"
                f"  failures: {[f.message for f in result.failures]}"
            )
            assert result.case_id == case.id

    @pytest.mark.parametrize(
        "case_id, wrong_decision",
        [
            ("allow.refund_status_check", "block"),
            ("block.payment_cancellation", "allow"),
            ("review.customer_data_lookup", "allow"),
        ],
    )
    def test_decision_mismatch_fails(self, case_id: str, wrong_decision: str):
        cases = load_evaluation_cases(GOLDEN_FILE)
        case = next(c for c in cases if c.id == case_id)
        events: list[RuntimeEvent] = []
        seq = 1
        for exp in case.expectations:
            if isinstance(exp, GovernanceDecisionExpectation):
                events.append(
                    event(
                        seq,
                        RuntimeEventType.GOVERNANCE_DECISION,
                        {"decision": wrong_decision, "allowed": wrong_decision == "allow"},
                    )
                )
                seq += 1

        result = EvaluationService().evaluate(events, [case])[0]

        assert not result.passed
        assert any(
            "Expected governance decision" in f.message for f in result.failures
        )

    def test_missing_expectation_fails(self):
        cases = load_evaluation_cases(GOLDEN_FILE)
        case = next(c for c in cases if c.id == "allow.refund_status_check")
        events: list[RuntimeEvent] = []
        for exp in case.expectations:
            if isinstance(exp, GovernanceDecisionExpectation):
                events.append(
                    event(
                        1,
                        RuntimeEventType.GOVERNANCE_DECISION,
                        {"decision": "allow", "allowed": True},
                    )
                )
                break
        events.append(event(2, RuntimeEventType.AGENT_MESSAGE, {"message": "no tool executed"}))

        result = EvaluationService().evaluate(events, [case])[0]

        assert not result.passed
        assert any("allowed_tool" in f.expectation_type for f in result.failures)

    def test_failure_output_identifies_case_and_expected(self):
        cases = load_evaluation_cases(GOLDEN_FILE)
        case = next(c for c in cases if c.id == "block.payment_cancellation")
        result = EvaluationService().evaluate([], [case])[0]

        assert not result.passed
        assert len(result.failures) > 0
        failure_messages = [f.message for f in result.failures]
        combined = " ".join(failure_messages)
        assert "block" in combined.lower() or "deny" in combined.lower()


class TestGoldenCaseCoverage:
    def test_covers_allow_block_review(self):
        cases = load_evaluation_cases(GOLDEN_FILE)
        decisions_seen: set[str] = set()
        for case in cases:
            for exp in case.expectations:
                if isinstance(exp, GovernanceDecisionExpectation) and exp.decision:
                    decisions_seen.add(exp.decision)

        assert "allow" in decisions_seen, "Must have at least one ALLOW golden case"
        assert "block" in decisions_seen, "Must have at least one BLOCK golden case"
        assert "require_review" in decisions_seen, "Must have at least one REVIEW golden case"

    def test_cases_declare_expected_decision_and_reason_evidence(self):
        cases = load_evaluation_cases(GOLDEN_FILE)
        for case in cases:
            has_decision = any(
                isinstance(exp, GovernanceDecisionExpectation) for exp in case.expectations
            )
            assert has_decision, f"Case '{case.id}' must declare a governance_decision expectation"


class TestGoldenCaseFailureReporting:
    def test_passed_case_reports_pass(self):
        cases = load_evaluation_cases(GOLDEN_FILE)
        case = next(c for c in cases if c.id == "allow.document_summary")
        events = _matching_events(case.expectations)

        result = EvaluationService().evaluate(events, [case])[0]

        assert result.passed
        assert result.case_id == "allow.document_summary"

    def test_failed_case_reports_failure_details(self):
        cases = load_evaluation_cases(GOLDEN_FILE)
        case = next(c for c in cases if c.id == "allow.document_summary")
        events: list[RuntimeEvent] = [
            event(
                1,
                RuntimeEventType.GOVERNANCE_DECISION,
                {"decision": "block", "allowed": False, "severity": "high"},
            )
        ]

        result = EvaluationService().evaluate(events, [case])[0]

        assert not result.passed
        assert all(f.expectation_type for f in result.failures)
        assert all(f.message for f in result.failures)
