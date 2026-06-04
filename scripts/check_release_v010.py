"""v0.1.0 release smoke check. Exit 0 if all checks pass."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

CHECKS_PASSED = []
CHECKS_FAILED = []


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
    print("Ailuros v0.1.0 release smoke check")
    print("=" * 40)

    # Version checks
    check_file_contains("pyproject.toml", 'version = "0.1.0"', "version = 0.1.0")

    init_path = ROOT / "src" / "ailuros" / "__init__.py"
    if init_path.exists():
        check_file_contains("src/ailuros/__init__.py", "0.1.0", "0.1.0")

    # Content checks
    check_file_contains("CHANGELOG.md", "0.1.0", "0.1.0")
    check_file_contains("README.md", "Ailuros", "Ailuros")

    # File existence checks
    check_file_exists("examples/hello.py")
    check_file_exists("docs/release/v0.1.0-checklist.md")
    check_file_exists("docs/release/v0.1.0-acceptance.md")
    check_file_exists("docs/contracts/governance-decision-contract.md")
    check_file_exists("scripts/check_repo_baseline.py")
    check_file_exists("scripts/check_docs_baseline.py")

    # Run hello example as a quick smoke test
    hello = ROOT / "examples" / "hello.py"
    if hello.exists():
        result = subprocess.run(
            [sys.executable, str(hello)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            ok("examples/hello.py runs without error")
        else:
            fail(f"examples/hello.py exited {result.returncode}: {result.stderr.strip()[:200]}")

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
