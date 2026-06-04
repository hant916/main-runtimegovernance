"""v0.2.0 release smoke check. Exit 0 if all checks pass. Stdlib only."""

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


def main() -> int:
    print("Ailuros v0.2.0 release smoke check")
    print("=" * 40)

    check_file_exists("docs/release/v0.2.0-acceptance.md")
    check_file_contains(
        "docs/release/v0.2.0-acceptance.md",
        "acceptance-defined",
        "acceptance-defined status",
    )
    check_file_contains(
        "docs/release/v0.2.0-acceptance.md",
        "evidence-only",
        "evidence-only",
    )
    check_file_contains(
        "docs/release/v0.2.0-acceptance.md",
        "HTTP write API",
        "HTTP write API non-goal",
    )

    check_file_exists("src/ailuros/models/evidence.py")
    check_file_exists("src/ailuros/evidence/__init__.py")
    check_file_exists("src/ailuros/evidence/ingest.py")
    check_file_exists("src/ailuros/evidence/export.py")

    check_file_exists("docs/contracts/phase1-evidence-only-contract.md")
    check_file_contains(
        "docs/contracts/phase1-evidence-only-contract.md",
        "evidence-only",
        "evidence-only",
    )

    check_file_exists("docs/strategy/phase1-readiness.md")

    check_file_exists("examples/reference_apps/fixtures/clarify_browser.json")
    check_file_exists("examples/reference_apps/fixtures/everrun_execution.json")
    check_file_exists("examples/reference_apps/fixtures/radarcreation_risk.json")

    check_file_exists("tests/test_evidence_contract.py")
    check_file_exists("tests/test_evidence_ingest.py")
    check_file_exists("tests/test_evidence_export.py")
    check_file_exists("tests/test_evidence_evaluation.py")
    check_file_exists("tests/test_evidence_regression.py")
    check_file_exists("tests/test_reference_app_fixtures.py")
    check_file_exists("tests/test_release_v020.py")

    check_file_exists("docs/release/v0.1.0-finalization.md")
    check_file_exists("scripts/check_repo_baseline.py")
    check_file_exists("scripts/check_docs_baseline.py")

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
