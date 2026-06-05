from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
AILUROS = REPO / "src" / "ailuros"
ADAPTERS = AILUROS / "adapters"
SERVER = AILUROS / "server"

FORBIDDEN_REFERENCE_TERMS: list[str] = [
    r"\bclarify\b",
    r"\bbrowser\b",
    r"\bsidepanel\b",
    r"\bcta\b",
    r"\bradarCreation\b",
]

EVIDENCE_WRITE_METHODS: list[str] = [
    "do_POST",
    "do_PUT",
    "do_PATCH",
    "do_DELETE",
]


def _core_py_files() -> list[Path]:
    py_files: list[Path] = []
    for py_file in AILUROS.rglob("*.py"):
        if ADAPTERS in py_file.parents:
            continue
        py_files.append(py_file)
    return sorted(py_files)


def check_reference_terms() -> list[str]:
    violations: list[str] = []
    for py_file in _core_py_files():
        content = py_file.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_REFERENCE_TERMS:
            if re.search(pattern, content, re.IGNORECASE):
                violations.append(f"{py_file}: matches {pattern!r}")
    return violations


def check_server_write_methods() -> list[str]:
    if not SERVER.is_dir():
        return []
    violations: list[str] = []
    for py_file in SERVER.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for method in EVIDENCE_WRITE_METHODS:
            if method in content:
                violations.append(f"{py_file}: defines {method}")
    return violations


def main() -> int:
    term_violations = check_reference_terms()
    write_violations = check_server_write_methods()

    all_ok = True

    if term_violations:
        all_ok = False
        print(f"FAIL: {len(term_violations)} reference-app term(s) found in core:")
        for v in term_violations:
            print(f"  {v}")

    if write_violations:
        all_ok = False
        print(f"FAIL: {len(write_violations)} HTTP write method(s) found in server:")
        for v in write_violations:
            print(f"  {v}")

    if all_ok:
        print("OK: evidence pipeline boundary is clean")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
