from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

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


class OutputFormat(StrEnum):
    text = "text"
    json = "json"
    jsonl = "jsonl"


class ReportFormat(StrEnum):
    json = "json"
    md = "md"


def _print_json(data: Any) -> None:
    typer.echo(json.dumps(data, indent=2, default=str))

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
def version(
    output: Annotated[
        OutputFormat,
        typer.Option("--output", help="Output format."),
    ] = OutputFormat.text,
) -> None:
    ver = AilurosRuntime().get_version()
    if output == OutputFormat.json:
        _print_json({"name": "ailuros", "version": ver})
    else:
        typer.echo(ver)


@app.command()
def replay(
    run_id: str,
    output: Annotated[
        OutputFormat,
        typer.Option("--output", help="Output format."),
    ] = OutputFormat.text,
) -> None:
    try:
        events = ReplayService(open_storage()).load_run(run_id)
    except (AilurosNotFoundError, AilurosDataCorruptionError, typer.BadParameter) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    if output == OutputFormat.json:
        _print_json({
            "run_id": run_id,
            "events": [e.model_dump(mode="json") for e in events],
        })
        return

    typer.echo(f"Run: {run_id}")
    typer.echo("Timeline:")
    for event in events:
        typer.echo(format_event(event))


@app.command()
def audit(
    run_id: str,
    output: Annotated[
        OutputFormat,
        typer.Option("--output", help="Output format."),
    ] = OutputFormat.text,
) -> None:
    try:
        events = ReplayService(open_storage()).load_run(run_id)
        summary = build_audit_summary(events)
    except (AilurosNotFoundError, AilurosDataCorruptionError, typer.BadParameter) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    if output == OutputFormat.json:
        _print_json({
            "run_id": run_id,
            "decision": summary.decision,
            "reason": summary.reason,
            "tool": summary.tool,
            "path_validation": summary.path_validation,
        })
        return

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
    output: Annotated[
        OutputFormat,
        typer.Option("--output", help="Output format."),
    ] = OutputFormat.text,
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

    if output == OutputFormat.json:
        _print_json({
            "run_id": run_id,
            "results": [r.model_dump(mode="json") for r in results],
            "summary": {"passed": len(results) - len(failed), "failed": len(failed)},
        })
        if failed:
            raise typer.Exit(1)
        return

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


@app.command()
def audit_package(
    run_id: str,
    output_dir: Annotated[
        Path | None,
        typer.Option(
            "--output-dir",
            help="Write audit package files to this directory instead of stdout.",
        ),
    ] = None,
    output: Annotated[
        OutputFormat,
        typer.Option("--output", help="Output format (stdout only)."),
    ] = OutputFormat.json,
) -> None:
    from ailuros.audit.package_export import export_audit_package_json
    from ailuros.audit_package import export_audit_package_to_dir
    from ailuros.cli_run import open_storage

    try:
        storage = open_storage()
    except typer.BadParameter as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    if output_dir is not None:
        try:
            pkg_path = export_audit_package_to_dir(storage, run_id, output_dir.resolve())
        except (AilurosNotFoundError, AilurosDataCorruptionError) as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1) from exc
        typer.echo(str(pkg_path))
        return

    try:
        result = export_audit_package_json(storage, run_id)
    except (AilurosNotFoundError, AilurosDataCorruptionError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    typer.echo(result)


@app.command()
def evidence(
    run_id: str,
    output: Annotated[
        OutputFormat,
        typer.Option("--output", help="Output format: json or jsonl."),
    ] = OutputFormat.json,
) -> None:
    from ailuros.cli_run import open_storage
    from ailuros.evidence.export import export_evidence_json, export_evidence_jsonl

    try:
        storage = open_storage()
    except typer.BadParameter as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    try:
        if output == OutputFormat.jsonl:
            result = export_evidence_jsonl(storage, run_id)
        else:
            result = export_evidence_json(storage, run_id)
    except (AilurosNotFoundError, AilurosDataCorruptionError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    typer.echo(result)


@app.command("evidence-audit")
def evidence_audit(
    package_path: Path,
    format: Annotated[
        ReportFormat,
        typer.Option("--format", help="Report format: json or md."),
    ] = ReportFormat.json,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Write the report to this file instead of stdout."),
    ] = None,
) -> None:
    """Audit a canonical evidence package on disk and render a post-run report.

    This is post-run validation, not runtime governance: it inspects a completed
    run's evidence and reports a pass/warn/fail decision. No allow/review/block
    control is performed.
    """
    from ailuros.adapters.evidence_package import (
        audit_evidence_package,
        audit_result_to_json,
        audit_result_to_markdown,
    )

    if not package_path.is_dir():
        typer.echo(f"evidence package directory not found: {package_path}", err=True)
        raise typer.Exit(1)

    result = audit_evidence_package(package_path)
    if format == ReportFormat.md:
        rendered = audit_result_to_markdown(result)
    else:
        rendered = audit_result_to_json(result)

    if out is not None:
        out.write_text(rendered, encoding="utf-8")
        typer.echo(str(out))
        return

    typer.echo(rendered)


@app.command("validate-package")
def validate_package(package_dir: Path) -> None:
    from ailuros.audit_package import validate_audit_package_dir

    result = validate_audit_package_dir(package_dir)
    _print_json(result.to_dict())
    if not result.valid:
        raise typer.Exit(1)


@app.command()
def server(
    host: Annotated[
        str,
        typer.Option("--host", help="Bind address. Default 127.0.0.1 (localhost only)."),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option("--port", help="Listen port."),
    ] = 8000,
    db: Annotated[
        Path | None,
        typer.Option("--db", help="SQLite database path."),
    ] = None,
) -> None:
    from ailuros.server import run_server

    try:
        storage = open_storage(db)
    except typer.BadParameter as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    try:
        run_server(storage=storage, host=host, port=port)
    except OSError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
