from pathlib import Path
from typing import Annotated

import typer

from ailuros.cli_policy import app as policy_app
from ailuros.cli_run import app as run_app
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
    if db is not None:
        from ailuros.cli_run import set_db_override

        set_db_override(db)


@app.command()
def version() -> None:
    typer.echo(AilurosRuntime().get_version())
