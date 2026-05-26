import json

from typer.testing import CliRunner

from ailuros.cli import app


def test_regression_compare_all_pass(tmp_path):
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps({"metadata": {}, "cases": {"a": {"expected_passed": True}}}),
        encoding="utf-8",
    )
    results = tmp_path / "results.json"
    results.write_text(
        json.dumps([{"case_id": "a", "passed": True, "failures": [], "evidence": []}]),
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["regression", "compare", str(results), str(baseline)])

    assert result.exit_code == 0
    assert "All clear" in result.output
    assert "Compared 1 case(s)" in result.output


def test_regression_compare_fails_on_regression(tmp_path):
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps({"metadata": {}, "cases": {"a": {"expected_passed": True}}}),
        encoding="utf-8",
    )
    results = tmp_path / "results.json"
    results.write_text(
        json.dumps([{"case_id": "a", "passed": False, "failures": [], "evidence": []}]),
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["regression", "compare", str(results), str(baseline)])

    assert result.exit_code == 1
    assert "REGRESSION" in result.output
    assert "pass_to_fail" in result.output


def test_regression_compare_with_warning_passes(tmp_path):
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps({"metadata": {}, "cases": {"a": {"expected_passed": True}}}),
        encoding="utf-8",
    )
    results = tmp_path / "results.json"
    results.write_text(
        json.dumps([
            {"case_id": "a", "passed": True, "failures": [], "evidence": []},
            {"case_id": "b", "passed": True, "failures": [], "evidence": []},
        ]),
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["regression", "compare", str(results), str(baseline)])

    assert result.exit_code == 0
    assert "WARNING" in result.output


def test_regression_compare_invalid_baseline(tmp_path):
    baseline = tmp_path / "baseline.json"
    baseline.write_text("not json", encoding="utf-8")
    results = tmp_path / "results.json"
    results.write_text("[]", encoding="utf-8")

    result = CliRunner().invoke(app, ["regression", "compare", str(results), str(baseline)])

    assert result.exit_code == 1
    assert "invalid baseline file" in result.output


def test_regression_compare_invalid_results(tmp_path):
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps({"metadata": {}, "cases": {}}),
        encoding="utf-8",
    )
    results = tmp_path / "results.json"
    results.write_text("not an array", encoding="utf-8")

    result = CliRunner().invoke(app, ["regression", "compare", str(results), str(baseline)])

    assert result.exit_code == 1
    assert "invalid current results file" in result.output


def test_regression_compare_results_not_a_list(tmp_path):
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps({"metadata": {}, "cases": {}}),
        encoding="utf-8",
    )
    results = tmp_path / "results.json"
    results.write_text('{"not": "a list"}', encoding="utf-8")

    result = CliRunner().invoke(app, ["regression", "compare", str(results), str(baseline)])

    assert result.exit_code == 1
    assert "must be a JSON array" in result.output
