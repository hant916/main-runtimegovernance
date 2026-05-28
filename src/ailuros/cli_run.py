from __future__ import annotations

import json
import os
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import typer

from ailuros.errors import AilurosDataCorruptionError, AilurosNotFoundError
from ailuros.models import RuntimeEvent
from ailuros.storage import SQLiteStorage


class OutputFormat(StrEnum):
    text = "text"
    json = "json"


def _print_json(data: Any) -> None:
    typer.echo(json.dumps(data, indent=2, default=str))

app = typer.Typer(help="Inspect runs and timelines.")
_db_override: Path | None = None


def set_db_override(path: Path | None) -> None:
    global _db_override
    _db_override = path


def resolve_db(path: Path | None = None) -> Path:
    return path or _db_override or Path(os.environ.get("AILUROS_DB", "ailuros.sqlite"))


def open_storage(path: Path | None = None) -> SQLiteStorage:
    db_path = resolve_db(path)
    if not db_path.exists():
        raise typer.BadParameter(f"database not found: {db_path}")
    storage = SQLiteStorage(db_path)
    storage.init()
    return storage


@app.command("list")
def list_runs() -> None:
    try:
        runs = open_storage().list_runs()
    except typer.BadParameter as exc:
        raise typer.Exit(1) from exc
    if not runs:
        typer.echo("No runs found.")
        return
    for run in runs:
        typer.echo(f"{run.run_id} {run.status.value} {run.created_at.isoformat()} {run.agent_id}")


@app.command("show")
def show_run(
    run_id: str,
    output: Annotated[
        OutputFormat,
        typer.Option("--output", help="Output format."),
    ] = OutputFormat.text,
) -> None:
    try:
        storage = open_storage()
        run = storage.get_run(run_id)
        events = storage.list_events(run_id)
    except (AilurosNotFoundError, AilurosDataCorruptionError, typer.BadParameter) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    if output == OutputFormat.json:
        _print_json({
            "run_id": run.run_id,
            "status": run.status.value,
            "agent_id": run.agent_id,
            "events": [e.model_dump(mode="json") for e in events],
        })
        return

    typer.echo(f"Run: {run.run_id}")
    typer.echo(f"Status: {run.status.value}")
    typer.echo(f"Agent: {run.agent_id}")
    typer.echo("Timeline:")
    for event in events:
        typer.echo(format_event(event))


def format_event(event: RuntimeEvent) -> str:
    payload = event.payload or {}
    highlight = ""
    if event.event_type.value in {
        "tool_call_requested",
        "governance_decision",
        "tool_call_blocked",
        "evaluation_result",
    }:
        highlight = " " + json.dumps(payload, sort_keys=True)
    seq = event.sequence if event.sequence is not None else "-"
    return f"{seq}: {event.event_type.value}{highlight}"
