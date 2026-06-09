"""v1.6 release hardening checker. Exit 0 if all checks pass. Stdlib only."""

import subprocess
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


def check_non_goal_absent(path: str, forbidden: str, label: str) -> None:
    p = ROOT / path
    if not p.exists():
        return
    content = p.read_text(encoding="utf-8")
    if forbidden in content:
        fail(f"{label} found in {path} (non-goal)")
    else:
        ok(f"{label} absent from {path} (non-goal preserved)")


def main() -> int:
    print("Ailuros v1.6 release hardening checker")
    print("=" * 40)

    # ------------------------------------------------------------------
    # 1. v1.5 closure still holds
    # ------------------------------------------------------------------
    print("--- v1.5 closure ---")
    v150_checker = ROOT / "scripts" / "check_release_v150.py"
    if v150_checker.exists():
        result = subprocess.run(
            [sys.executable, str(v150_checker)],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        if result.returncode == 0:
            ok("v1.5 closure checker passed")
        else:
            fail(f"v1.5 closure checker failed (exit {result.returncode})")
    else:
        fail("scripts/check_release_v150.py missing")

    # Key v1.5 source files still present
    check_file_exists("src/ailuros/adapters/evidence_package/loader.py")
    check_file_exists("src/ailuros/adapters/evidence_package/validator.py")
    check_file_exists("src/ailuros/adapters/evidence_package/audit.py")
    check_file_exists("src/ailuros/adapters/evidence_package/markdown_report.py")
    check_file_exists("src/ailuros/adapters/evidence_package/__init__.py")

    # ------------------------------------------------------------------
    # 2. Golden fixture validation (v1.6 PASS/WARN/FAIL)
    # ------------------------------------------------------------------
    print("--- golden fixtures ---")
    for outcome in ("pass-governance-run", "warn-anomaly-run", "fail-contract-run"):
        pkg_dir = ROOT / "fixtures" / "ailuros" / "v160" / outcome
        if pkg_dir.is_dir():
            ok(f"fixtures/ailuros/v160/{outcome}/ exists")
        else:
            fail(f"fixtures/ailuros/v160/{outcome}/ missing")
            continue
        for fname in ("manifest.json", "timeline.json"):
            if (pkg_dir / fname).is_file():
                ok(f"fixtures/ailuros/v160/{outcome}/{fname} exists")
            else:
                fail(f"fixtures/ailuros/v160/{outcome}/{fname} missing")

    # ------------------------------------------------------------------
    # 3. Golden fixture tests
    # ------------------------------------------------------------------
    print("--- golden fixture tests ---")
    check_file_exists("tests/test_v160_golden_audit_fixtures.py")
    check_file_contains(
        "tests/test_v160_golden_audit_fixtures.py",
        "test_pass_audit_decision",
        "PASS audit decision test",
    )
    check_file_contains(
        "tests/test_v160_golden_audit_fixtures.py",
        "test_warn_audit_decision",
        "WARN audit decision test",
    )
    check_file_contains(
        "tests/test_v160_golden_audit_fixtures.py",
        "test_fail_audit_decision",
        "FAIL audit decision test",
    )
    check_file_contains(
        "tests/test_v160_golden_audit_fixtures.py",
        "test_all_outcomes_distinct",
        "distinct outcomes test",
    )

    # Run golden fixture tests as subprocess
    golden_test = ROOT / "tests" / "test_v160_golden_audit_fixtures.py"
    if golden_test.exists():
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(golden_test), "-q", "--no-header"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        if result.returncode == 0:
            ok("test_v160_golden_audit_fixtures.py passed")
        else:
            fail(f"test_v160_golden_audit_fixtures.py failed (exit {result.returncode})")

    # ------------------------------------------------------------------
    # 4. Report-quality regression tests
    # ------------------------------------------------------------------
    print("--- report quality ---")
    check_file_exists("tests/test_v160_audit_report_quality.py")
    check_file_contains(
        "tests/test_v160_audit_report_quality.py",
        "## Decision",
        "Decision section requirement",
    )
    check_file_contains(
        "tests/test_v160_audit_report_quality.py",
        "test_report_output_is_deterministic",
        "deterministic report test",
    )
    check_file_contains(
        "tests/test_v160_audit_report_quality.py",
        "test_three_fixtures_produce_distinct_reports",
        "distinct reports test",
    )

    # Run report quality tests as subprocess
    quality_test = ROOT / "tests" / "test_v160_audit_report_quality.py"
    if quality_test.exists():
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(quality_test), "-q", "--no-header"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        if result.returncode == 0:
            ok("test_v160_audit_report_quality.py passed")
        else:
            fail(f"test_v160_audit_report_quality.py failed (exit {result.returncode})")

    # ------------------------------------------------------------------
    # 5. Docs boundary checks
    # ------------------------------------------------------------------
    print("--- docs boundary ---")
    check_file_exists("README.md")
    check_file_contains("README.md", "v1.5", "v1.5 mention")
    check_file_exists("docs/strategy/roadmap.md")
    check_file_contains("docs/strategy/roadmap.md", "v1.5", "v1.5 section")
    check_file_contains("docs/strategy/roadmap.md", "v2.0", "v2.0 section")

    # ------------------------------------------------------------------
    # 6. Non-goals: v2.0 HTTP ingestion out of scope
    # ------------------------------------------------------------------
    print("--- non-goals ---")
    check_non_goal_absent(
        "src/ailuros/adapters/evidence_package/__init__.py",
        "http",
        "HTTP ingestion",
    )
    check_non_goal_absent(
        "src/ailuros/adapters/evidence_package/__init__.py",
        "server",
        "server",
    )
    check_non_goal_absent(
        "src/ailuros/adapters/evidence_package/__init__.py",
        "block",
        "runtime block",
    )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print()
    print(f"Passed: {len(CHECKS_PASSED)}  Failed: {len(CHECKS_FAILED)}")
    if CHECKS_FAILED:
        for msg in CHECKS_FAILED:
            print(f"  - {msg}")
        return 1
    print("v1.6 hardening: PASS")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "src"))
    sys.exit(main())
