import json
from pathlib import Path

import pytest

from ailuros import AilurosRuntime, GovernanceDecisionType

GOLDEN_DIR = Path(__file__).parent / "golden"


def _load_fixtures():
    fixtures = []
    for f in sorted(GOLDEN_DIR.glob("*.json")):
        data = json.loads(f.read_text())
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
