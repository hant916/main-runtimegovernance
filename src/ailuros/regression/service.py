from ailuros.evaluation.models import EvaluationResult
from ailuros.regression.models import RegressionBaseline, RegressionComparisonResult, RegressionDiff


class RegressionService:
    def compare(
        self,
        current_results: list[EvaluationResult],
        baseline: RegressionBaseline,
    ) -> RegressionComparisonResult:
        current_by_id: dict[str, EvaluationResult] = {r.case_id: r for r in current_results}
        regressions: list[RegressionDiff] = []
        warnings: list[RegressionDiff] = []

        for case_id, baseline_case in baseline.cases.items():
            if case_id not in current_by_id:
                regressions.append(
                    RegressionDiff(
                        case_id=case_id,
                        kind="missing_from_current",
                        message=f"Baseline case {case_id!r} is missing from current results",
                        baseline_expected_passed=baseline_case.expected_passed,
                        current_passed=None,
                    )
                )
                continue

            current = current_by_id[case_id]
            if baseline_case.expected_passed and not current.passed:
                regressions.append(
                    RegressionDiff(
                        case_id=case_id,
                        kind="pass_to_fail",
                        message=(
                            f"Baseline expected PASS for {case_id!r} but current is FAIL "
                            f"(expected {baseline_case.expected_failure_count} failures, "
                            f"got {len(current.failures)})"
                        ),
                        baseline_expected_passed=True,
                        current_passed=False,
                    )
                )

        for case_id, current in current_by_id.items():
            if case_id not in baseline.cases:
                if not current.passed:
                    regressions.append(
                        RegressionDiff(
                            case_id=case_id,
                            kind="unexpected_new_fail",
                            message=(
                                f"New case {case_id!r} not in baseline but current is FAIL "
                                f"({len(current.failures)} failure(s))"
                            ),
                            baseline_expected_passed=None,
                            current_passed=False,
                        )
                    )
                else:
                    warnings.append(
                        RegressionDiff(
                            case_id=case_id,
                            kind="new_passing_case",
                            message=f"New case {case_id!r} not in baseline -- PASS (informational)",
                            baseline_expected_passed=None,
                            current_passed=True,
                        )
                    )

        all_ids = sorted(set(baseline.cases.keys()) | set(current_by_id.keys()))

        return RegressionComparisonResult(
            passed=not regressions,
            case_ids_compared=all_ids,
            regressions=regressions,
            warnings=warnings,
        )
