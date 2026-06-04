from __future__ import annotations

from typing import Any

from ailuros.evaluation.models import EvaluationResult
from ailuros.regression.models import (
    EvidenceTimelineDiff,
    EvidenceTimelineRegressionResult,
    RegressionBaseline,
    RegressionComparisonResult,
    RegressionDiff,
)


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

    @staticmethod
    def _extract_evidence_signature(record: dict[str, Any]) -> dict[str, Any]:
        evidence = record.get("evidence") or {}
        if not isinstance(evidence, dict):
            evidence = {}
        return {
            "sequence": record.get("sequence"),
            "event_type": record.get("event_type"),
            "evidence_version": evidence.get("version"),
            "evidence_event_type": evidence.get("event_type"),
        }

    def compare_evidence_timeline(
        self,
        baseline: list[dict[str, Any]],
        current: list[dict[str, Any]],
    ) -> EvidenceTimelineRegressionResult:
        diffs: list[EvidenceTimelineDiff] = []
        max_len = max(len(baseline), len(current))

        for i in range(max_len):
            base_rec = baseline[i] if i < len(baseline) else None
            curr_rec = current[i] if i < len(current) else None

            if base_rec is None:
                diffs.append(
                    EvidenceTimelineDiff(
                        index=i,
                        kind="added_evidence",
                        message=(
                            f"Additional evidence event at position {i} "
                            f"not present in baseline"
                        ),
                        current_record=curr_rec,
                    )
                )
                continue

            if curr_rec is None:
                diffs.append(
                    EvidenceTimelineDiff(
                        index=i,
                        kind="missing_evidence",
                        message=(
                            f"Baseline evidence event at position {i} "
                            f"missing from current"
                        ),
                        baseline_record=base_rec,
                    )
                )
                continue

            base_sig = self._extract_evidence_signature(base_rec)
            curr_sig = self._extract_evidence_signature(curr_rec)

            if base_sig != curr_sig:
                field_diffs: list[str] = []
                for key in base_sig:
                    if base_sig[key] != curr_sig[key]:
                        field_diffs.append(
                            f"{key}: {base_sig[key]!r} -> {curr_sig[key]!r}"
                        )

                diffs.append(
                    EvidenceTimelineDiff(
                        index=i,
                        kind="changed_evidence",
                        message=(
                            f"Evidence changed at position {i}: "
                            + "; ".join(field_diffs)
                        ),
                        baseline_record=base_rec,
                        current_record=curr_rec,
                    )
                )

        return EvidenceTimelineRegressionResult(
            passed=not diffs,
            baseline_count=len(baseline),
            current_count=len(current),
            diffs=diffs,
        )
