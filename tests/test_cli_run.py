from typer.testing import CliRunner

from ailuros import AilurosRuntime
from ailuros.cli import app


def test_run_list_missing_database(monkeypatch, tmp_path):
    monkeypatch.delenv("AILUROS_DB", raising=False)
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["run", "list"])

    assert result.exit_code != 0


def test_run_list_and_show_with_db_path(tmp_path):
    db = tmp_path / "runtime.sqlite"
    runtime = AilurosRuntime(storage_path=db)
    run = runtime.start_run("hello")

    listed = CliRunner().invoke(app, ["--db", str(db), "run", "list"])
    shown = CliRunner().invoke(app, ["--db", str(db), "run", "show", run.run_id])

    assert listed.exit_code == 0
    assert run.run_id in listed.output
    assert shown.exit_code == 0
    assert "1: run_started" in shown.output


def test_run_list_with_env_db(monkeypatch, tmp_path):
    db = tmp_path / "runtime.sqlite"
    AilurosRuntime(storage_path=db).start_run("hello")
    monkeypatch.setenv("AILUROS_DB", str(db))

    result = CliRunner().invoke(app, ["run", "list"])

    assert result.exit_code == 0
    assert "run_" in result.output


def test_unknown_run_show_exits_nonzero(tmp_path):
    db = tmp_path / "runtime.sqlite"
    AilurosRuntime(storage_path=db)

    result = CliRunner().invoke(app, ["--db", str(db), "run", "show", "run_missing"])

    assert result.exit_code != 0
