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
        _print_json(
            {
                "run_id": run_id,
                "events": [e.model_dump(mode="json") for e in events],
            }
        )
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
        _print_json(
            {
                "run_id": run_id,
                "decision": summary.decision,
                "reason": summary.reason,
                "tool": summary.tool,
                "path_validation": summary.path_validation,
            }
        )
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
        cases = [case for case_file in case_files for case in load_evaluation_cases(case_file)]
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
        _print_json(
            {
                "run_id": run_id,
                "results": [r.model_dump(mode="json") for r in results],
                "summary": {"passed": len(results) - len(failed), "failed": len(failed)},
            }
        )
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


@app.command()
def report(
    run_id: str,
    format: Annotated[
        ReportFormat,
        typer.Option("--format", "-f", help="Report format: json or md."),
    ] = ReportFormat.json,
    rebuild: Annotated[
        bool,
        typer.Option("--rebuild", help="Rebuild the execution projection before reporting."),
    ] = False,
) -> None:
    """Produce a deterministic per-run governance report.

    Reads the stored execution projection and signals for a run and
    renders a summary report. Errors are written to stderr and the
    command exits nonzero.

    If no projection exists, use --rebuild to regenerate it from raw
    events, or run the projection rebuild step separately.
    """
    from ailuros.core.execution import ExecutionProjection
    from ailuros.execution_report import (
        build_run_report,
        render_run_report_json,
        render_run_report_markdown,
    )
    from ailuros.projection import rebuild_projections_and_signals
    from ailuros.signals import GovernanceSignal

    try:
        storage = open_storage()
        storage.get_run(run_id)
    except (AilurosNotFoundError, typer.BadParameter) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    if rebuild:
        try:
            rebuild_projections_and_signals(storage, run_id)
        except (AilurosNotFoundError, AilurosDataCorruptionError) as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1) from exc

    stored = storage.get_projection(run_id)
    if stored is None:
        typer.echo(
            f"No projection found for run {run_id}. "
            "Rebuild it with --rebuild or run the projection step separately.",
            err=True,
        )
        raise typer.Exit(1)

    projection = ExecutionProjection.model_validate(stored["projection"])

    signal_dicts = storage.get_signals(run_id)
    signal_rule_version = signal_dicts[0].get("rule_version", "1.0.0") if signal_dicts else "1.0.0"
    signals = [
        GovernanceSignal.model_validate({**s, "rule_version": signal_rule_version})
        for s in signal_dicts
    ]

    report_obj = build_run_report(projection, signals)

    if format == ReportFormat.md:
        rendered = render_run_report_markdown(report_obj)
    else:
        rendered = render_run_report_json(report_obj)

    typer.echo(rendered)


@app.command()
def diagnose(
    run_id: str,
    format: Annotated[
        ReportFormat,
        typer.Option("--format", "-f", help="Diagnosis format: json or md."),
    ] = ReportFormat.json,
    rebuild: Annotated[
        bool,
        typer.Option("--rebuild", help="Rebuild the execution projection before diagnosing."),
    ] = False,
) -> None:
    """Produce a deterministic advisory diagnosis for a run.

    Reads the stored execution projection and signals and renders the four
    bounded diagnosis fields: incomplete work, root-cause class, current risk,
    and next action recommendation. The diagnosis is advisory only: it never
    edits a pack, widens scope, or mutates runtime state.
    """
    from ailuros.core.execution import ExecutionProjection
    from ailuros.projection import rebuild_projections_and_signals
    from ailuros.run_diagnosis import (
        diagnose_run,
        render_diagnosis_json,
        render_diagnosis_markdown,
    )
    from ailuros.signals import GovernanceSignal

    try:
        storage = open_storage()
        storage.get_run(run_id)
    except (AilurosNotFoundError, typer.BadParameter) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    if rebuild:
        try:
            rebuild_projections_and_signals(storage, run_id)
        except (AilurosNotFoundError, AilurosDataCorruptionError) as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1) from exc

    stored = storage.get_projection(run_id)
    if stored is None:
        typer.echo(
            f"No projection found for run {run_id}. "
            "Rebuild it with --rebuild or run the projection step separately.",
            err=True,
        )
        raise typer.Exit(1)

    projection = ExecutionProjection.model_validate(stored["projection"])

    signal_dicts = storage.get_signals(run_id)
    signal_rule_version = signal_dicts[0].get("rule_version", "1.0.0") if signal_dicts else "1.0.0"
    signals = [
        GovernanceSignal.model_validate({**s, "rule_version": signal_rule_version})
        for s in signal_dicts
    ]

    diagnosis = diagnose_run(projection, signals)

    if format == ReportFormat.md:
        rendered = render_diagnosis_markdown(diagnosis)
    else:
        rendered = render_diagnosis_json(diagnosis)

    typer.echo(rendered)


@app.command("correlate-failures")
def correlate_failures(
    run_ids: Annotated[
        list[str],
        typer.Argument(
            help=(
                "Finite run ids to correlate. Correlation consumes exactly the "
                "supplied runs; no storage scan discovers related runs."
            ),
        ),
    ],
    format: Annotated[
        ReportFormat,
        typer.Option("--format", "-f", help="Output format: json or md."),
    ] = ReportFormat.json,
    rebuild: Annotated[
        bool,
        typer.Option(
            "--rebuild",
            help="Rebuild each run's projection before diagnosing and correlating.",
        ),
    ] = False,
) -> None:
    """Correlate bounded run failures across a caller-supplied finite run set.

    Each supplied run id is projected to a canonical diagnosis via ``diagnose_run``
    and the diagnoses are correlated with ``correlate_run_failures``. The input is
    exactly the run ids supplied: no history scan discovers related runs, and an
    omitted or nonexistent run fails rather than being silently dropped. The result
    is advisory and read-only; it never returns ``accept`` or mutates runtime state.
    """
    from ailuros.core.execution import ExecutionProjection
    from ailuros.projection import rebuild_projections_and_signals
    from ailuros.run_diagnosis import RunDiagnosis, diagnose_run
    from ailuros.run_failure_correlation import (
        correlate_run_failures,
        render_correlation_json,
        render_correlation_markdown,
    )
    from ailuros.signals import GovernanceSignal

    if not run_ids:
        typer.echo("at least one RUN_ID is required", err=True)
        raise typer.Exit(1)

    try:
        storage = open_storage()
    except typer.BadParameter as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    diagnoses: list[RunDiagnosis] = []
    for run_id in run_ids:
        try:
            storage.get_run(run_id)
        except (AilurosNotFoundError, typer.BadParameter) as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1) from exc

        if rebuild:
            try:
                rebuild_projections_and_signals(storage, run_id)
            except (AilurosNotFoundError, AilurosDataCorruptionError) as exc:
                typer.echo(str(exc), err=True)
                raise typer.Exit(1) from exc

        stored = storage.get_projection(run_id)
        if stored is None:
            typer.echo(
                f"No projection found for run {run_id}. "
                "Rebuild it with --rebuild or run the projection step separately.",
                err=True,
            )
            raise typer.Exit(1)

        projection = ExecutionProjection.model_validate(stored["projection"])

        signal_dicts = storage.get_signals(run_id)
        signal_rule_version = (
            signal_dicts[0].get("rule_version", "1.0.0") if signal_dicts else "1.0.0"
        )
        signals = [
            GovernanceSignal.model_validate({**s, "rule_version": signal_rule_version})
            for s in signal_dicts
        ]

        diagnoses.append(diagnose_run(projection, signals))

    correlation = correlate_run_failures(diagnoses)

    if format == ReportFormat.md:
        rendered = render_correlation_markdown(correlation)
    else:
        rendered = render_correlation_json(correlation)

    typer.echo(rendered)


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
    else:
        typer.echo(rendered)

    if not result.ok:
        raise typer.Exit(1)


@app.command("evidence-conformance")
def evidence_conformance(
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
    """Report per-capability governance evidence conformance for a package.

    Reads only canonical structured events and reports, for each Ailuros
    governance capability, whether the package carries enough canonical evidence
    to evaluate it. This is evidence sufficiency reporting, not structural
    package validation and not runtime governance.
    """
    from ailuros.evidence_conformance import (
        conformance_result_to_json,
        conformance_result_to_markdown,
        evaluate_evidence_conformance,
    )

    if not package_path.is_dir():
        typer.echo(f"evidence package directory not found: {package_path}", err=True)
        raise typer.Exit(1)

    result = evaluate_evidence_conformance(package_path)
    if format == ReportFormat.md:
        rendered = conformance_result_to_markdown(result)
    else:
        rendered = conformance_result_to_json(result)

    if out is not None:
        out.write_text(rendered, encoding="utf-8")
        typer.echo(str(out))
    else:
        typer.echo(rendered)

    if not result.package_valid:
        raise typer.Exit(1)


@app.command("import-evidence-package")
def import_evidence_package(
    package_dir: Path,
) -> None:
    from ailuros.adapters.evidence_package import (
        ImportStatus,
        ingest_evidence_package,
        load_evidence_package,
    )
    from ailuros.cli_run import open_storage

    try:
        storage = open_storage()
    except typer.BadParameter as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    try:
        package = load_evidence_package(package_dir)
    except (FileNotFoundError, ValueError) as exc:
        _print_json({"status": "invalid", "detail": str(exc)})
        raise typer.Exit(1) from exc

    try:
        result = ingest_evidence_package(storage, package)
    except Exception as exc:
        _print_json({"status": "invalid", "detail": str(exc)})
        raise typer.Exit(1) from exc

    _print_json(result.model_dump(mode="json"))

    if result.status == ImportStatus.CONFLICT:
        raise typer.Exit(1)


@app.command("batch-import")
def batch_import(
    root_dir: Path,
) -> None:
    if not root_dir.is_dir():
        typer.echo(f"directory not found: {root_dir}", err=True)
        raise typer.Exit(1)

    try:
        storage = open_storage()
    except typer.BadParameter as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    from ailuros.backfill import batch_import_project

    summary = batch_import_project(storage, root_dir)
    _print_json(summary.model_dump(mode="json"))

    if summary.invalid > 0 or summary.conflict > 0 or summary.projection_failed > 0:
        raise typer.Exit(1)


@app.command("validate-package")
def validate_package(package_dir: Path) -> None:
    from ailuros.audit_package import validate_audit_package_dir

    result = validate_audit_package_dir(package_dir)
    _print_json(result.to_dict())
    if result.decision == "FAIL":
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
