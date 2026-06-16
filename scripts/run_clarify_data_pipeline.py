from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def _fail_result(output_dir: Path, clarify_root: Path) -> None:
    source_bundle = clarify_root / "artifacts" / "ailuros" / "latest"
    failure = {
        "schema_version": "ailuros.validation_result.v0",
        "source": "clarify",
        "status": "FAIL",
        "checks": [
            {
                "check": "clarify_bundle_exists",
                "status": "FAIL",
                "message": f"Clarify bundle not found: {source_bundle}",
            }
        ],
        "summary": {
            "total": 1,
            "passed": 0,
            "warnings": 0,
            "blocking_issues": 1,
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "ailuros-validation-result.json"
    result_path.write_text(
        json.dumps(failure, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    md_lines = [
        "# Ailuros Clarify Data Pipeline Report",
        "",
        "**Status:** FAIL",
        "Source: clarify",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        "| Total Checks | 1 |",
        "| Passed | 0 |",
        "| Warnings | 0 |",
        "| Blocking Issues | 1 |",
        "",
        "## Checks",
        "",
        "| # | Check | Status | Message |",
        "|---|---|---|---|",
        f"| 1 | clarify_bundle_exists | FAIL | Clarify bundle not found: {source_bundle} |",
    ]
    report_path = output_dir / "ailuros-validation-report.md"
    report_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Clarify data production and Ailuros offline processing"
    )
    parser.add_argument(
        "--clarify-root",
        required=True,
        help="Path to the Clarify repository root",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output directory for copied bundle and validation results",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="Profile to forward to the Clarify npm script",
    )
    parser.add_argument(
        "--skip-clarify-command",
        action="store_true",
        help="Skip the Clarify npm command (use existing bundle at artifacts/ailuros/latest)",
    )
    args = parser.parse_args()

    clarify_root = Path(args.clarify_root).resolve()
    output_dir = Path(args.output).resolve()
    source_bundle = clarify_root / "artifacts" / "ailuros" / "latest"

    if not clarify_root.is_dir():
        print(f"ERROR: --clarify-root does not exist: {clarify_root}", file=sys.stderr)
        return 1

    if not (clarify_root / "package.json").is_file():
        print(f"ERROR: package.json not found in {clarify_root}", file=sys.stderr)
        return 1

    if not args.skip_clarify_command:
        npm_exe = shutil.which("npm") or shutil.which("npm.cmd")
        if npm_exe is None:
            print("ERROR: npm not found on PATH", file=sys.stderr)
            return 1

        npm_cmd = [npm_exe, "run", "ailuros:produce-data"]
        if args.profile:
            npm_cmd.extend(["--", "--profile", args.profile])

        result = subprocess.run(
            npm_cmd,
            cwd=str(clarify_root),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(
                f"Clarify command exited with code {result.returncode}",
                file=sys.stderr,
            )
            if result.stdout:
                print(result.stdout, file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)

    if not source_bundle.is_dir():
        _fail_result(output_dir, clarify_root)
        print("Ailuros Clarify data pipeline: FAIL", file=sys.stderr)
        return 1

    if output_dir.exists():
        for item in output_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    for item in source_bundle.iterdir():
        if item.is_dir():
            shutil.copytree(item, output_dir / item.name)
        else:
            shutil.copy2(item, output_dir / item.name)

    base = Path(__file__).resolve().parent
    processor = base / "process_clarify_evidence_data.py"
    if not processor.is_file():
        print(f"ERROR: Processor not found: {processor}", file=sys.stderr)
        return 1

    proc_cmd = [sys.executable, str(processor), "--bundle", str(output_dir)]
    proc_result = subprocess.run(proc_cmd, capture_output=True, text=True)
    if proc_result.stdout:
        print(proc_result.stdout, end="")
    if proc_result.stderr:
        print(proc_result.stderr, file=sys.stderr, end="")

    validation_result_path = output_dir / "ailuros-validation-result.json"
    if validation_result_path.is_file():
        try:
            data = json.loads(validation_result_path.read_text(encoding="utf-8"))
            status = data.get("status", "FAIL")
        except (json.JSONDecodeError, OSError):
            status = "FAIL"
    else:
        status = "FAIL"

    status_label = "PASS" if status == "PASS" else "WARN" if status == "WARN" else "FAIL"
    print(f"Ailuros Clarify data pipeline: {status_label}")

    return proc_result.returncode


if __name__ == "__main__":
    sys.exit(main())
