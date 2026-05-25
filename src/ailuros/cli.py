from pathlib import Path
from typing import Annotated

import typer

from ailuros.audit import build_audit_summary
from ailuros.cli_policy import app as policy_app
from ailuros.cli_run import app as run_app
from ailuros.cli_run import format_event, open_storage
from ailuros.errors import AilurosDataCorruptionError, AilurosNotFoundError
from ailuros.replay import ReplayService
from ailuros.runtime import AilurosRuntime

app = typer.Typer(help="Ailuros Governance Runtime")
app.add_typer(run_app, name="run")
app.add_typer(policy_app, name="policy")


@app.callback()
def main(
    db: Annotated[
        Path | None,
        typer.Option("--db", help="SQLite database path for commands that inspect runtime state."),
    ] = None,
) -> None:
    from ailuros.cli_run import set_db_override

    set_db_override(db)


@app.command()
def version() -> None:
    typer.echo(AilurosRuntime().get_version())


@app.command()
def replay(run_id: str) -> None:
    try:
        events = ReplayService(open_storage()).load_run(run_id)
    except (AilurosNotFoundError, AilurosDataCorruptionError, typer.BadParameter) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    typer.echo(f"Run: {run_id}")
    typer.echo("Timeline:")
    for event in events:
        typer.echo(format_event(event))


@app.command()
def audit(run_id: str) -> None:
    try:
        events = ReplayService(open_storage()).load_run(run_id)
        summary = build_audit_summary(events)
    except (AilurosNotFoundError, AilurosDataCorruptionError, typer.BadParameter) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    typer.echo(f"Run: {run_id}")
    typer.echo("Audit:")
    typer.echo(f"Decision: {summary.decision}")
    typer.echo(f"Reason: {summary.reason}")
    typer.echo(f"Tool: {summary.tool}")
    typer.echo(f"Path validation: {summary.path_validation}")
