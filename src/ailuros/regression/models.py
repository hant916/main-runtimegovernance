from typing import Any

from pydantic import BaseModel, ConfigDict


class RegressionBaselineCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_passed: bool
    expected_failure_count: int = 0


class RegressionBaseline(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metadata: dict[str, str] = {}
    cases: dict[str, RegressionBaselineCase]


class RegressionDiff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    kind: str
    message: str
    baseline_expected_passed: bool | None = None
    current_passed: bool | None = None


class RegressionComparisonResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    case_ids_compared: list[str]
    regressions: list[RegressionDiff]
    warnings: list[RegressionDiff]


class EvidenceTimelineDiff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int | None
    kind: str
    message: str
    baseline_record: dict[str, Any] | None = None
    current_record: dict[str, Any] | None = None


class EvidenceTimelineRegressionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    baseline_count: int
    current_count: int
    diffs: list[EvidenceTimelineDiff]
