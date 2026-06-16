from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Clarify evidence export and Ailuros offline validation"
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
        "--skip-clarify-command",
        action="store_true",
        help="Skip the Clarify npm command (use existing bundle at artifacts/ailuros/latest)",
    )
    args = parser.parse_args()

    clarify_root = Path(args.clarify_root).resolve()
    output_dir = Path(args.output).resolve()

    if not clarify_root.is_dir():
        print(f"ERROR: --clarify-root does not exist: {clarify_root}", file=sys.stderr)
        return 1

    package_json = clarify_root / "package.json"
    if not package_json.is_file():
        print(f"ERROR: package.json not found in {clarify_root}", file=sys.stderr)
        return 1

    base = Path(__file__).resolve().parent
    validator = base / "validate_clarify_evidence_bundle.py"
    if not validator.is_file():
        print(f"ERROR: Validator not found: {validator}", file=sys.stderr)
        return 1

    source_bundle = clarify_root / "artifacts" / "ailuros" / "latest"

    if not args.skip_clarify_command:
        npm_exe = shutil.which("npm") or shutil.which("npm.cmd")
        if npm_exe is None:
            print("ERROR: npm not found on PATH", file=sys.stderr)
            return 1

        result = subprocess.run(
            [npm_exe, "run", "ailuros:evidence"],
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
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_missing_bundle_failure(output_dir, source_bundle)
        return 1

    if output_dir.exists():
        for item in output_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    expected_files = [
        "manifest.json",
        "ailuros.timeline.v0.json",
        "clarify-validation.log",
        "clarify-validation-result.json",
        "README.md",
    ]
    for fname in expected_files:
        src = source_bundle / fname
        if src.is_file():
            shutil.copy2(src, output_dir / fname)

    validator_cmd = [sys.executable, str(validator), "--bundle", str(output_dir)]
    val_result = subprocess.run(validator_cmd, capture_output=True, text=True)
    if val_result.stdout:
        print(val_result.stdout, end="")
    if val_result.stderr:
        print(val_result.stderr, file=sys.stderr, end="")

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
    print(f"Ailuros Clarify validation: {status_label}")

    return val_result.returncode


def _write_missing_bundle_failure(output_dir: Path, source_bundle: Path) -> None:
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
    result_path = output_dir / "ailuros-validation-result.json"
    result_path.write_text(
        json.dumps(failure, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    md_lines = [
        "# Ailuros Clarify Validation Report",
        "",
        "**Status:** FAIL",
        "**Source:** clarify",
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

    print("Ailuros Clarify validation: FAIL", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
