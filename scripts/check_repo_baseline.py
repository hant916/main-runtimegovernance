"""check_repo_baseline.py — deterministic v0.1.0 release-baseline sanity check.

Exits 0 if all release prerequisites are met, non-zero otherwise.
Does not require network access, git history, or external services.
"""

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _check(ok: bool, label: str, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    msg = f"  [{status}] {label}"
    if detail:
        msg += f"  ({detail})" if ok else f"  — {detail}"
    print(msg)
    return ok


def check_version() -> bool:
    path = REPO / "pyproject.toml"
    if not path.is_file():
        return _check(False, "pyproject.toml exists", "file not found")
    text = path.read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        return _check(False, "version in pyproject.toml", "version field missing")
    ok = m.group(1) == "0.1.0"
    return _check(ok, f"version is 0.1.0", f"found {m.group(1)!r}" if not ok else "")


def check_changelog() -> bool:
    path = REPO / "CHANGELOG.md"
    if not path.is_file():
        return _check(False, "CHANGELOG.md exists", "file not found")
    text = path.read_text(encoding="utf-8")
    ok = "v0.1.0" in text
    return _check(ok, "CHANGELOG.md mentions v0.1.0", "no v0.1.0 section found" if not ok else "")


def check_hello_demo() -> bool:
    path = REPO / "examples" / "hello.py"
    ok = path.is_file()
    return _check(ok, "examples/hello.py exists", "file not found" if not ok else "")


def check_adr_docs() -> bool:
    adr_dir = REPO / "docs" / "decisions"
    if not adr_dir.is_dir():
        return _check(False, "docs/decisions/ directory exists", "directory not found")
    expected = [
        "ADR-0001-ailuros-as-governance-runtime.md",
        "ADR-0002-clarify-as-reference-app.md",
        "ADR-0003-evidence-first-integration.md",
    ]
    results = []
    for name in expected:
        path = adr_dir / name
        ok = path.is_file()
        _check(ok, f"docs/decisions/{name} exists", "file not found" if not ok else "")
        results.append(ok)
    return all(results)


def check_roadmap() -> bool:
    path = REPO / "docs" / "strategy" / "roadmap.md"
    if not path.is_file():
        return _check(False, "docs/strategy/roadmap.md exists", "file not found")
    text = path.read_text(encoding="utf-8")
    ok = "Phase 5" in text
    return _check(ok, "roadmap.md exists with Phase 5", "")


def check_phase5_deferral() -> bool:
    path = REPO / "docs" / "strategy" / "roadmap.md"
    if not path.is_file():
        return _check(False, "Phase 5 deferral documented", "roadmap.md not found")
    text = path.read_text(encoding="utf-8")
    ok = "explicitly deferred" in text or "Phase 5 — Platformization" in text
    return _check(ok, "Phase 5 deferral is documented in roadmap.md",
                  "no deferral language found" if not ok else "")


def check_readme_refers_to_demo() -> bool:
    path = REPO / "README.md"
    if not path.is_file():
        return _check(False, "README.md exists", "file not found")
    text = path.read_text(encoding="utf-8")
    ok = "hello.py" in text or "refund_agent" in text or "main.py" in text
    return _check(ok, "README references hello demo or runnable example",
                  "no reference found" if not ok else "")


def main() -> int:
    print(f"v0.1.0 release-baseline sanity check for {REPO.name}")
    print()

    checks = [
        ("Version", check_version),
        ("Changelog", check_changelog),
        ("Hello demo", check_hello_demo),
        ("ADR docs", check_adr_docs),
        ("Roadmap", check_roadmap),
        ("Phase 5 deferral", check_phase5_deferral),
        ("README→demo cross-ref", check_readme_refers_to_demo),
    ]

    results = []
    for label, fn in checks:
        results.append(fn())

    print()
    passed = sum(results)
    total = len(results)
    print(f"  {passed}/{total} checks passed")

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
