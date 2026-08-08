"""v0.3.0 release smoke check. Exit 0 if all checks pass. Stdlib only."""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

CHECKS_PASSED: list[str] = []
CHECKS_FAILED: list[str] = []


def ok(msg: str) -> None:
    CHECKS_PASSED.append(msg)
    print(f"  ok  {msg}")


def fail(msg: str) -> None:
    CHECKS_FAILED.append(msg)
    print(f"FAIL  {msg}")


def check_file_exists(path: str) -> bool:
    p = ROOT / path
    if p.exists():
        ok(f"{path} exists")
        return True
    fail(f"{path} missing")
    return False


def check_file_contains(path: str, substring: str, label: str) -> None:
    p = ROOT / path
    if not p.exists():
        fail(f"{path} missing (cannot check for {label!r})")
        return
    if substring in p.read_text(encoding="utf-8"):
        ok(f"{path} contains {label!r}")
    else:
        fail(f"{path} does not contain {label!r}")


def check_substring_in_any(paths: list[str], substring: str, label: str) -> None:
    for path in paths:
        p = ROOT / path
        if p.exists() and substring in p.read_text(encoding="utf-8"):
            ok(f"{label!r} found in {path}")
            return
    fail(f"{label!r} not found in any of {paths}")


def main() -> int:
    print("Ailuros v0.3.0 release smoke check")
    print("=" * 40)

    check_file_exists("docs/release/v0.3.0-acceptance.md")
    check_file_contains(
        "docs/release/v0.3.0-acceptance.md",
        "Status: accepted",
        "accepted status",
    )
    check_file_contains(
        "docs/release/v0.3.0-acceptance.md",
        "IMPLEMENTED",
        "IMPLEMENTED rows",
    )
    check_file_contains(
        "docs/release/v0.3.0-acceptance.md",
        "NON-GOAL",
        "NON-GOAL rows",
    )
    check_file_contains(
        "docs/release/v0.3.0-acceptance.md",
        "Audit package exporter",
        "Audit package exporter",
    )
    check_file_contains(
        "docs/release/v0.3.0-acceptance.md",
        "Refund governance demo",
        "Refund governance demo",
    )
    check_file_contains(
        "docs/release/v0.3.0-acceptance.md",
        "Release acceptance gate",
        "Release acceptance gate",
    )

    non_goals = [
        "UI dashboard",
        "server write API",
        "production integrations",
        "broad adapter ecosystem",
        "agent orchestration",
        "MCP Gateway",
    ]
    for ng in non_goals:
        check_file_contains(
            "docs/release/v0.3.0-acceptance.md",
            ng,
            f"non-goal: {ng}",
        )

    check_file_exists("docs/release/v0.3.0-scope.md")
    check_file_exists("docs/release/v0.3.0-finalization.md")

    check_file_exists("src/ailuros/audit_package/__init__.py")
    check_file_contains(
        "src/ailuros/audit_package/__init__.py",
        "export_audit_package_to_dir",
        "export_audit_package_to_dir",
    )

    check_file_exists("src/ailuros/audit/package_export.py")
    check_file_contains(
        "src/ailuros/audit/package_export.py",
        "export_audit_package",
        "export_audit_package",
    )

    check_file_exists("examples/refund_governance_demo.py")
    check_file_contains(
        "examples/refund_governance_demo.py",
        "def run_demo",
        "run_demo function",
    )

    check_file_exists("tests/test_audit_package.py")
    check_file_contains(
        "tests/test_audit_package.py",
        "ailuros.audit-package.v1",
        "audit-package.v1 schema marker",
    )
    check_file_exists("tests/test_audit_package_export.py")
    check_file_exists("tests/test_refund_governance_demo.py")
    check_file_exists("tests/test_refund_demo.py")
    check_file_exists("tests/test_release_v030.py")

    check_file_exists("docs/release/v0.2.0-acceptance.md")
    check_file_exists("scripts/check_release_v020.py")

    print("=" * 40)
    print(f"Passed: {len(CHECKS_PASSED)}  Failed: {len(CHECKS_FAILED)}")

    if CHECKS_FAILED:
        print("\nFailed checks:")
        for msg in CHECKS_FAILED:
            print(f"  - {msg}")
        return 1

    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
