from __future__ import annotations

import sys
from pathlib import Path

EXIT_PASS = 0
EXIT_FAIL = 1
MAX_LOG_BYTES = 10 * 1024 * 1024


def _check_raw_log(bundle_dir: Path) -> str | None:
    log_path = bundle_dir / "clarify-validation.log"
    if not log_path.is_file():
        return "raw_log_missing"
    try:
        size = log_path.stat().st_size
    except OSError:
        return "raw_log_unreadable"
    if size == 0:
        return "raw_log_empty"
    if size > MAX_LOG_BYTES:
        return "raw_log_oversized"
    return None


def main() -> int:
    if len(sys.argv) < 3 or sys.argv[1] != "--bundle":
        print(
            "Usage: python scripts/process_clarify_evidence_data.py "
            "--bundle <bundle-dir>",
            file=sys.stderr,
        )
        return EXIT_FAIL

    bundle_dir = Path(sys.argv[2]).resolve()
    if not bundle_dir.is_dir():
        print(f"Bundle directory not found: {bundle_dir}", file=sys.stderr)
        return EXIT_FAIL

    _THIS_DIR = Path(__file__).resolve().parent
    if str(_THIS_DIR.parent) not in sys.path:
        sys.path.insert(0, str(_THIS_DIR.parent))

    from scripts.validate_clarify_evidence_bundle import (
        validate_bundle,
        write_results,
    )

    checks, status = validate_bundle(bundle_dir)
    write_results(bundle_dir, checks, status)

    raw_log_issue = _check_raw_log(bundle_dir)
    if raw_log_issue:
        print(f"Warning: Raw log check: {raw_log_issue}", file=sys.stderr)

    print(f"Status: {status}")
    blocking = sum(1 for c in checks if c.status == "FAIL")
    warnings = sum(1 for c in checks if c.status == "WARN")
    print(f"Blocking issues: {blocking}, Warnings: {warnings}")

    for c in checks:
        if c.status != "PASS":
            print(f"  [{c.status}] {c.name}: {c.message}")

    if status == "FAIL":
        return EXIT_FAIL
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
