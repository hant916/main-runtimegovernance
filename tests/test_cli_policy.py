from typer.testing import CliRunner

from ailuros.cli import app


def test_policy_validate_cli_success():
    result = CliRunner().invoke(
        app, ["policy", "validate", "tests/policy/fixtures/valid_refund_policy.json"]
    )

    assert result.exit_code == 0
    assert "Validated 1 policy" in result.output


def test_policy_validate_cli_failure():
    result = CliRunner().invoke(
        app, ["policy", "validate", "tests/policy/fixtures/invalid_missing_id.json"]
    )

    assert result.exit_code != 0
    assert "policy_id" in result.output
