from typer.testing import CliRunner

from ailuros import AilurosRuntime
from ailuros.cli import app


def test_import_version_and_instantiation(tmp_path):
    runtime = AilurosRuntime(storage_path=tmp_path / "smoke.sqlite")

    assert runtime.name == "AilurosRuntime"
    assert runtime.get_version() == "0.3.0"


def test_cli_version():
    result = CliRunner().invoke(app, ["version"])

    assert result.exit_code == 0
    assert "0.3.0" in result.output
