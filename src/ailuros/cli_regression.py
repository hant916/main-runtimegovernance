from __future__ import annotations

import json
from pathlib import Path

import typer

from ailuros.evaluation.models import EvaluationResult
from ailuros.regression import RegressionService, replay_timeline
from ailuros.regression.models import RegressionBaseline

app = typer.Typer(help="Regression commands: compare baselines and replay timelines.")


@app.command("compare")
def compare(
    current_results: Path,
    baseline: Path,
) -> None:
    try:
        with open(current_results, encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, list):
            typer.echo("current_results must be a JSON array of EvaluationResult objects", err=True)
            raise typer.Exit(1)
        results = [EvaluationResult.model_validate(item) for item in raw]
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        typer.echo(f"invalid current results file: {exc}", err=True)
        raise typer.Exit(1) from exc

    try:
        with open(baseline, encoding="utf-8") as f:
            raw_baseline = json.load(f)
        baseline_obj = RegressionBaseline.model_validate(raw_baseline)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        typer.echo(f"invalid baseline file: {exc}", err=True)
        raise typer.Exit(1) from exc

    result = RegressionService().compare(results, baseline_obj)

    typer.echo(f"Compared {len(result.case_ids_compared)} case(s)")
    for diff in result.regressions:
        typer.echo(f"REGRESSION [{diff.kind}] {diff.case_id}: {diff.message}")
    for diff in result.warnings:
        typer.echo(f"WARNING  [{diff.kind}] {diff.case_id}: {diff.message}")

    if result.regressions:
        typer.echo(
            f"Regression: {len(result.regressions)} failure(s), "
            f"{len(result.warnings)} warning(s)"
        )
        raise typer.Exit(1)
    else:
        typer.echo(f"All clear -- {len(result.warnings)} informational warning(s)")


@app.command("replay")
def replay(
    timeline_path: Path = typer.Argument(  # noqa: B008
        ..., help="Path to a stored timeline JSON file (list of RuntimeEvent objects)."
    ),
) -> None:
    try:
        result = replay_timeline(timeline_path)
    except Exception as exc:
        typer.echo(f"unexpected error during replay: {exc}", err=True)
        raise typer.Exit(1) from exc

    if result.failures:
        typer.echo("Timeline replay regressions:", err=True)
        for failure in result.failures:
            typer.echo(f"  FAIL {failure}", err=True)

    typer.echo(
        f"Summary: {result.total_cases} case(s), "
        f"{result.passed_cases} passed, "
        f"{result.failed_cases} failed"
    )

    if not result.passed:
        raise typer.Exit(1)
