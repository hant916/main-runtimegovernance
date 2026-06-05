from __future__ import annotations

import sys
from pathlib import Path

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
if str(EXAMPLES) not in sys.path:
    sys.path.insert(0, str(EXAMPLES))

from refund_governance_demo import FIXTURES, run_demo  # noqa: E402

_AUDIT_PACKAGE_FILES = [
    "manifest.json",
    "run.json",
    "timeline.jsonl",
    "decisions.json",
    "evaluations.json",
    "regressions.json",
    "summary.md",
]


def test_low_refund_is_allowed(tmp_path: Path) -> None:
    result = run_demo(tmp_path / "output")
    decisions = {d["case_id"]: d for d in result["fixture_decisions"]}
    d = decisions["refund-low-eligible"]
    assert d["actual_decision"] == "allow"
    assert d["expected_decision"] == "allow"


def test_high_refund_requires_review(tmp_path: Path) -> None:
    result = run_demo(tmp_path / "output")
    decisions = {d["case_id"]: d for d in result["fixture_decisions"]}
    d = decisions["refund-high-eligible"]
    assert d["actual_decision"] == "require_review"
    assert d["expected_decision"] == "require_review"
    reason_lower = d["reason"].lower()
    assert any(word in reason_lower for word in ["threshold", "approval", "limit"]), (
        f"Reason must mention threshold, approval, or limit; got: {d['reason']}"
    )


def test_invalid_pnr_not_allowed(tmp_path: Path) -> None:
    result = run_demo(tmp_path / "output")
    decisions = {d["case_id"]: d for d in result["fixture_decisions"]}
    d = decisions["refund-invalid-pnr"]
    assert d["actual_decision"] != "allow"
    assert d["expected_decision"] == "block"


def test_audit_package_has_required_files(tmp_path: Path) -> None:
    result = run_demo(tmp_path / "output")
    pkg_dir = Path(result["audit_package_dir"])
    assert pkg_dir.is_dir()
    for filename in _AUDIT_PACKAGE_FILES:
        assert (pkg_dir / filename).exists(), f"Missing audit package file: {filename}"


def test_output_only_in_requested_directory(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    other_dir = tmp_path / "other"
    result = run_demo(output_dir)
    pkg_dir = Path(result["audit_package_dir"])
    assert str(pkg_dir.resolve()).startswith(str(output_dir.resolve()))
    assert not other_dir.exists() or not any(other_dir.iterdir())


def test_all_fixtures_produce_expected_decisions(tmp_path: Path) -> None:
    result = run_demo(tmp_path / "output")
    decisions = {d["case_id"]: d for d in result["fixture_decisions"]}
    for fixture in FIXTURES:
        d = decisions[fixture["case_id"]]
        assert d["actual_decision"] == fixture["expected_decision"], (
            f"{fixture['case_id']}: expected {fixture['expected_decision']}, "
            f"got {d['actual_decision']}"
        )


def test_evaluation_results_present(tmp_path: Path) -> None:
    result = run_demo(tmp_path / "output")
    assert len(result["eval_results"]) == len(FIXTURES)
    for ev in result["eval_results"]:
        assert "case_id" in ev
        assert "passed" in ev
