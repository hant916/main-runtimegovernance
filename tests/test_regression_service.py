import pytest
from pydantic import ValidationError

from ailuros.evaluation.models import EvaluationFailure, EvaluationResult
from ailuros.regression import RegressionService
from ailuros.regression.models import RegressionBaseline, RegressionBaselineCase, RegressionDiff


def _result(case_id: str, passed: bool) -> EvaluationResult:
    return EvaluationResult(
        case_id=case_id,
        passed=passed,
        failures=[EvaluationFailure(expectation_type="test", message="fail")] if not passed else [],
        evidence=[],
    )


class TestRegressionBaselineValidation:
    def test_invalid_field_rejected(self):
        with pytest.raises(ValidationError):
            RegressionBaseline.model_validate(
                {"cases": {"c": {"expected_passed": True, "extra": 1}}}
            )

    def test_baseline_case_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            RegressionBaselineCase.model_validate({"expected_passed": True, "unknown": "x"})


class TestRegressionComparison:
    def test_all_pass_no_regression(self):
        baseline = RegressionBaseline(
            cases={
                "a": RegressionBaselineCase(expected_passed=True),
                "b": RegressionBaselineCase(expected_passed=True),
            }
        )
        results = [_result("a", True), _result("b", True)]

        comp = RegressionService().compare(results, baseline)

        assert comp.passed is True
        assert comp.regressions == []
        assert comp.warnings == []

    def test_pass_to_fail_is_hard_regression(self):
        baseline = RegressionBaseline(
            cases={"a": RegressionBaselineCase(expected_passed=True)}
        )
        results = [_result("a", False)]

        comp = RegressionService().compare(results, baseline)

        assert comp.passed is False
        assert len(comp.regressions) == 1
        assert comp.regressions[0].kind == "pass_to_fail"
        assert comp.regressions[0].case_id == "a"

    def test_baseline_fail_still_fail_is_not_regression(self):
        baseline = RegressionBaseline(
            cases={"a": RegressionBaselineCase(expected_passed=False)}
        )
        results = [_result("a", False)]

        comp = RegressionService().compare(results, baseline)

        assert comp.passed is True
        assert comp.regressions == []

    def test_baseline_fail_now_pass_is_not_regression(self):
        baseline = RegressionBaseline(
            cases={"a": RegressionBaselineCase(expected_passed=False)}
        )
        results = [_result("a", True)]

        comp = RegressionService().compare(results, baseline)

        assert comp.passed is True
        assert comp.regressions == []

    def test_missing_case_is_hard_regression(self):
        baseline = RegressionBaseline(
            cases={
                "a": RegressionBaselineCase(expected_passed=True),
                "b": RegressionBaselineCase(expected_passed=True),
            }
        )
        results = [_result("a", True)]

        comp = RegressionService().compare(results, baseline)

        assert comp.passed is False
        assert len(comp.regressions) == 1
        assert comp.regressions[0].kind == "missing_from_current"
        assert comp.regressions[0].case_id == "b"

    def test_unexpected_new_fail_is_hard_regression(self):
        baseline = RegressionBaseline(
            cases={"a": RegressionBaselineCase(expected_passed=True)}
        )
        results = [_result("a", True), _result("b", False)]

        comp = RegressionService().compare(results, baseline)

        assert comp.passed is False
        assert len(comp.regressions) == 1
        assert comp.regressions[0].kind == "unexpected_new_fail"
        assert comp.regressions[0].case_id == "b"

    def test_new_passing_case_is_warning_not_hard_regression(self):
        baseline = RegressionBaseline(
            cases={"a": RegressionBaselineCase(expected_passed=True)}
        )
        results = [_result("a", True), _result("b", True)]

        comp = RegressionService().compare(results, baseline)

        assert comp.passed is True
        assert comp.regressions == []
        assert len(comp.warnings) == 1
        assert comp.warnings[0].kind == "new_passing_case"
        assert comp.warnings[0].case_id == "b"

    def test_multiple_regressions_all_reported(self):
        baseline = RegressionBaseline(
            cases={
                "a": RegressionBaselineCase(expected_passed=True),
                "b": RegressionBaselineCase(expected_passed=True),
            }
        )
        results = [_result("a", False), _result("c", False)]

        comp = RegressionService().compare(results, baseline)

        assert comp.passed is False
        kinds = {d.kind for d in comp.regressions}
        assert kinds == {"pass_to_fail", "missing_from_current", "unexpected_new_fail"}
        assert len(comp.regressions) == 3

    def test_case_ids_compared_includes_all_ids(self):
        baseline = RegressionBaseline(
            cases={"a": RegressionBaselineCase(expected_passed=True)}
        )
        results = [_result("a", True), _result("b", True)]

        comp = RegressionService().compare(results, baseline)

        assert sorted(comp.case_ids_compared) == ["a", "b"]

    def test_regression_diff_fields_set_correctly(self):
        baseline = RegressionBaseline(
            cases={"a": RegressionBaselineCase(expected_passed=True)}
        )
        results = [_result("a", False)]

        comp = RegressionService().compare(results, baseline)

        diff = comp.regressions[0]
        assert diff.baseline_expected_passed is True
        assert diff.current_passed is False
        assert isinstance(diff.message, str)
        assert len(diff.message) > 0

    def test_baseline_with_expected_failure_count(self):
        baseline = RegressionBaseline(
            cases={"a": RegressionBaselineCase(expected_passed=True, expected_failure_count=0)}
        )
        results = [_result("a", True)]

        comp = RegressionService().compare(results, baseline)
        assert comp.passed is True


class TestRegressionComparisonResultModel:
    def test_extra_fields_rejected(self):
        with pytest.raises(ValidationError):
            RegressionDiff.model_validate({
                "case_id": "a",
                "kind": "pass_to_fail",
                "message": "x",
                "extra": "bad",
            })
