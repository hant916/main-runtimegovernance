from pathlib import Path
from typing import Annotated

import typer

from ailuros.audit import build_audit_summary
from ailuros.cli_policy import app as policy_app
from ailuros.cli_regression import app as regression_app
from ailuros.cli_run import app as run_app
from ailuros.cli_run import format_event, open_storage
from ailuros.errors import AilurosDataCorruptionError, AilurosNotFoundError
from ailuros.evaluation import EvaluationCaseLoadError, EvaluationService, load_evaluation_cases
from ailuros.replay import ReplayService
from ailuros.runtime import AilurosRuntime

app = typer.Typer(help="Ailuros Governance Runtime")
app.add_typer(run_app, name="run")
app.add_typer(policy_app, name="policy")
app.add_typer(regression_app, name="regression")


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


@app.command("eval")
def eval_run(
    run_id: str,
    case_files: Annotated[
        list[Path] | None,
        typer.Option(
            "--case",
            help="EvaluationCase JSON file. May be provided more than once.",
        ),
    ] = None,
) -> None:
    if not case_files:
        typer.echo("at least one --case file is required", err=True)
        raise typer.Exit(1)

    try:
        events = ReplayService(open_storage()).load_run(run_id)
        cases = [
            case
            for case_file in case_files
            for case in load_evaluation_cases(case_file)
        ]
        results = EvaluationService().evaluate(events, cases)
    except (
        AilurosNotFoundError,
        AilurosDataCorruptionError,
        EvaluationCaseLoadError,
        typer.BadParameter,
    ) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    failed = [result for result in results if not result.passed]
    typer.echo(f"Evaluation: {run_id}")
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(f"{status} {result.case_id}")
        for failure in result.failures:
            typer.echo(f"  failure[{failure.expectation_type}]: {failure.message}")
        for evidence in result.evidence:
            event_type = evidence.event_type.value if evidence.event_type else "none"
            sequence = evidence.sequence if evidence.sequence is not None else "-"
            typer.echo(
                f"  evidence[{evidence.expectation_type}]: "
                f"seq={sequence} event={event_type} {evidence.message}"
            )
    typer.echo(f"Summary: {len(results) - len(failed)} passed, {len(failed)} failed")
    if failed:
        raise typer.Exit(1)
