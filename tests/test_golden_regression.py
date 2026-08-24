import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ailuros import AilurosRuntime, GovernanceDecisionType
from ailuros.core.execution import (
    DecisionSummary,
    ExecutionProjection,
    GovernanceCoverage,
    Lifecycle,
    Outcome,
    Scope,
    Validation,
)
from ailuros.regression import (
    GovernanceDimension,
    compare_governance_projections,
)

GOLDEN_DIR = Path(__file__).parent / "golden"
REGRESSION_GOLDEN = GOLDEN_DIR / "regression" / "real_everrun_pair.json"


def _load_fixtures():
    fixtures = []
    for f in sorted(GOLDEN_DIR.glob("*.json")):
        data = json.loads(f.read_text())
        if not isinstance(data, dict):
            continue
        fixtures.append(pytest.param(data, id=data["name"]))
    return fixtures


def _write_policy(tmp_path: Path, policy_dict: dict) -> Path:
    path = tmp_path / f"{policy_dict['policy_id']}.json"
    path.write_text(json.dumps(policy_dict))
    return path


@pytest.mark.parametrize("fixture", _load_fixtures())
def test_golden_regression(fixture: dict, tmp_path: Path) -> None:
    runtime = AilurosRuntime(
        storage_path=tmp_path / "runtime.sqlite",
        policies=[_write_policy(tmp_path, p) for p in fixture.get("policies", [])],
    )
    run = runtime.start_run(fixture["name"])
    inp = fixture["input"]
    decision = runtime.before_tool_call(
        run.run_id,
        inp["tool_name"],
        inp.get("arguments"),
        inp.get("metadata"),
    )
    expected = GovernanceDecisionType(fixture["expected_decision"])

    assert decision.decision == expected, (
        f"Golden case '{fixture['name']}' failed:\n"
        f"  expected: {expected.value}\n"
        f"  actual:   {decision.decision.value}\n"
        f"  reason:   {decision.reason}"
    )


def _projection_from_facts(facts: dict) -> ExecutionProjection:
    now = datetime.now(UTC)
    coverage_values = facts.get("governance_coverage", {})
    coverage = GovernanceCoverage(
        validation=coverage_values.get("validation", "unknown"),
        scope=coverage_values.get("scope", "unknown"),
    )
    return ExecutionProjection(
        run_id=facts["run_id"],
        source="everrun",
        schema_version="1.0",
        lifecycle=Lifecycle(facts["lifecycle"]),
        outcome=Outcome(facts["outcome"]),
        validation=Validation(facts["validation"]),
        scope=Scope(facts["scope"]),
        started_at=now,
        decisions=[
            DecisionSummary(domain=decision["domain"], decision=decision["decision"])
            for decision in facts.get("decisions", [])
        ],
        governance_coverage=coverage,
    )


def _ordered_result(result) -> list[tuple[str, str, str, str]]:
    return [
        (item.dimension.value, item.baseline, item.current, item.transition.value)
        for item in result.dimensions
    ]


def test_golden_regression_real_everrun_pair() -> None:
    data = json.loads(REGRESSION_GOLDEN.read_text())
    baseline = _projection_from_facts(data["baseline"])
    current = _projection_from_facts(data["current"])

    expected = {
        row["dimension"]: (row["baseline"], row["current"], row["transition"])
        for row in data["expected"]
    }

    result = compare_governance_projections(baseline, current)

    assert result.baseline_run_id == data["baseline"]["run_id"]
    assert result.current_run_id == data["current"]["run_id"]
    actual = {
        item.dimension.value: (item.baseline, item.current, item.transition.value)
        for item in result.dimensions
    }
    assert actual == expected, (
        f"Golden regression case '{data['name']}' failed:\n"
        f"  expected: {expected}\n"
        f"  actual:   {actual}"
    )
    assert len(result.dimensions) == len(tuple(GovernanceDimension))
    assert [item.dimension for item in result.dimensions] == list(GovernanceDimension)


def test_golden_regression_real_everrun_pair_is_deterministic() -> None:
    data = json.loads(REGRESSION_GOLDEN.read_text())
    baseline = _projection_from_facts(data["baseline"])
    current = _projection_from_facts(data["current"])

    first = _ordered_result(compare_governance_projections(baseline, current))
    canonical_order = list(GovernanceDimension)
    for _ in range(5):
        repeat = _ordered_result(compare_governance_projections(baseline, current))
        assert repeat == first
        assert repeat == sorted(
            repeat, key=lambda row: canonical_order.index(GovernanceDimension(row[0]))
        )
