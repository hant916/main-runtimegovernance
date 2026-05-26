from __future__ import annotations

import json
from pathlib import Path

import typer

from ailuros.evaluation.models import EvaluationResult
from ailuros.regression import RegressionService
from ailuros.regression.models import RegressionBaseline

app = typer.Typer(help="Compare evaluation results against a saved baseline.")


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
