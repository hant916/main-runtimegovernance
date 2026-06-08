"""v1.5 release closure checker. Exit 0 if all checks pass. Stdlib only."""

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


def check_module_imports(module: str, names: list[str]) -> None:
    """Check that a Python module exists and exports the given names."""
    try:
        import importlib
        mod = importlib.import_module(module)
        for name in names:
            if hasattr(mod, name):
                ok(f"{module}.{name} importable")
            else:
                fail(f"{module}.{name} not found")
    except ImportError as e:
        fail(f"{module} not importable: {e}")


def check_clarify_handoff_validates() -> None:
    """Run validate_clarify_handoff.py as a subprocess (C-008R1)."""
    script = ROOT / "scripts" / "validate_clarify_handoff.py"
    if not script.exists():
        fail("scripts/validate_clarify_handoff.py missing (C-008R1)")
        return
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    if result.returncode == 0:
        ok("C-008R1 handoff validation passed")
    else:
        fail(f"C-008R1 handoff validation failed (exit {result.returncode})")


def check_non_goal_absent(path: str, forbidden: str, label: str) -> None:
    """Fail if `forbidden` is found in `path`."""
    p = ROOT / path
    if not p.exists():
        return
    content = p.read_text(encoding="utf-8")
    if forbidden in content:
        fail(f"{label} found in {path} (non-goal)")
    else:
        ok(f"{label} absent from {path} (non-goal preserved)")


def main() -> int:
    print("Ailuros v1.5 release closure checker")
    print("=" * 40)

    # --- Release doc ---
    check_file_exists("docs/release/v1.5-post-run-governance.md")
    check_file_contains(
        "docs/release/v1.5-post-run-governance.md",
        "**Status:** Accepted",
        "Status: Accepted",
    )

    # --- Contract doc ---
    check_file_exists("docs/contracts/evidence-package-post-run-governance-v15.md")
    check_file_contains(
        "docs/contracts/evidence-package-post-run-governance-v15.md",
        "**Status:** Accepted",
        "Status: Accepted",
    )

    # --- Demo doc ---
    check_file_exists("docs/demo/evidence-package-v15-demo.md")

    # --- Five accepted v1.5 packs ---
    print("--- v1.5 packs ---")

    # C-008: Clarify evidence handoff
    check_file_exists("scripts/validate_clarify_handoff.py")
    check_file_contains(
        "scripts/validate_clarify_handoff.py",
        "validate_clarify_timeline",
        "validate_clarify_timeline",
    )

    # A-005R1: Package loader
    check_file_exists("src/ailuros/adapters/evidence_package/loader.py")
    check_file_contains(
        "src/ailuros/adapters/evidence_package/loader.py",
        "load_evidence_package",
        "load_evidence_package",
    )

    # A-005R2: Timeline contract validator
    check_file_exists("src/ailuros/adapters/evidence_package/validator.py")
    check_file_contains(
        "src/ailuros/adapters/evidence_package/validator.py",
        "validate_evidence_package_contract",
        "validate_evidence_package_contract",
    )

    # A-005R3: Minimal governance decision
    check_file_exists("src/ailuros/adapters/evidence_package/audit.py")
    check_file_contains(
        "src/ailuros/adapters/evidence_package/audit.py",
        "audit_evidence_package",
        "audit_evidence_package",
    )

    # A-006R: Markdown audit report
    check_file_exists("src/ailuros/adapters/evidence_package/markdown_report.py")
    check_file_contains(
        "src/ailuros/adapters/evidence_package/markdown_report.py",
        "audit_result_to_markdown",
        "audit_result_to_markdown",
    )

    # --- Public API surface ---
    print("--- public API ---")
    check_file_exists("src/ailuros/adapters/evidence_package/__init__.py")
    check_file_contains(
        "src/ailuros/adapters/evidence_package/__init__.py",
        "audit_evidence_package",
        "audit_evidence_package export",
    )
    check_file_contains(
        "src/ailuros/adapters/evidence_package/__init__.py",
        "load_evidence_package",
        "load_evidence_package export",
    )
    check_file_contains(
        "src/ailuros/adapters/evidence_package/__init__.py",
        "validate_evidence_package_contract",
        "validate_evidence_package_contract export",
    )
    check_file_contains(
        "src/ailuros/adapters/evidence_package/__init__.py",
        "audit_result_to_markdown",
        "audit_result_to_markdown export",
    )
    check_file_contains(
        "src/ailuros/adapters/evidence_package/__init__.py",
        "audit_result_to_dict",
        "audit_result_to_dict export",
    )
    check_file_contains(
        "src/ailuros/adapters/evidence_package/__init__.py",
        "audit_result_to_json",
        "audit_result_to_json export",
    )

    # --- Core types ---
    check_file_exists("src/ailuros/core/audit.py")
    check_file_contains(
        "src/ailuros/core/audit.py",
        "AuditResult",
        "AuditResult type",
    )
    check_file_contains(
        "src/ailuros/core/audit.py",
        "AuditDecision",
        "AuditDecision type",
    )
    check_file_exists("src/ailuros/core/report.py")
    check_file_contains(
        "src/ailuros/core/report.py",
        "render_audit_markdown",
        "render_audit_markdown",
    )

    # --- C-008R1 handoff ---
    print("--- C-008R1 handoff ---")
    check_clarify_handoff_validates()

    # --- Test fixtures ---
    print("--- test fixtures ---")
    check_file_exists("tests/fixtures/evidence_package/valid-v15/manifest.json")
    check_file_exists("tests/fixtures/evidence_package/valid-v15/timeline.json")

    # --- V1.5-specific tests ---
    check_file_exists("tests/test_evidence_package_loader.py")
    check_file_exists("tests/test_evidence_package_contract_validator.py")
    check_file_exists("tests/test_evidence_package_markdown_report.py")
    check_file_exists("tests/test_post_run_governance_decision.py")

    # --- Roadmap mentions v1.5 ---
    check_file_exists("docs/strategy/roadmap.md")
    check_file_contains(
        "docs/strategy/roadmap.md",
        "v1.5",
        "v1.5 section",
    )
    check_file_contains(
        "docs/strategy/roadmap.md",
        "C-008",
        "C-008 pack reference",
    )

    # --- Non-goals preserved ---
    print("--- non-goals ---")
    evidence_pkg_init = ROOT / "src" / "ailuros" / "adapters" / "evidence_package" / "__init__.py"
    for non_goal, label in [
        ("http", "HTTP"),
        ("block", "runtime block"),
        ("server", "server"),
    ]:
        if evidence_pkg_init.exists():
            content = evidence_pkg_init.read_text(encoding="utf-8").lower()
            if non_goal in content:
                fail(f"{label} reference in evidence_package __init__ (non-goal)")
            else:
                ok(f"{label} absent from evidence_package __init__ (non-goal preserved)")

    # --- Summary ---
    print("=" * 40)
    print(f"Passed: {len(CHECKS_PASSED)}  Failed: {len(CHECKS_FAILED)}")

    if CHECKS_FAILED:
        print("\nFailed checks:")
        for msg in CHECKS_FAILED:
            print(f"  - {msg}")
        return 1

    print("v1.5 closure: PASS")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "src"))
    sys.exit(main())
