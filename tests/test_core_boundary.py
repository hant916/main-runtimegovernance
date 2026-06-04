from __future__ import annotations

import re
from pathlib import Path

AILUROS = Path("src/ailuros")
ADAPTERS = AILUROS / "adapters"
SERVER = AILUROS / "server"

FORBIDDEN_CORE_TERMS: list[str] = [
    r"\bclarify\b",
    r"\bbrowser\b",
    r"\bsidepanel\b",
    r"\bcta\b",
]

WRITE_METHODS: list[str] = [
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


def test_no_reference_app_terms_in_core() -> None:
    violations: list[str] = []
    for py_file in _core_py_files():
        content = py_file.read_text(encoding="utf-8")
        for term_pattern in FORBIDDEN_CORE_TERMS:
            if re.search(term_pattern, content, re.IGNORECASE):
                violations.append(f"{py_file}: matches forbidden term pattern {term_pattern!r}")

    assert not violations, (
        f"Core boundary violation: {len(violations)} reference-app term(s) found in "
        f"src/ailuros/ (excluding adapters/):\n"
        + "\n".join(violations)
    )


def test_server_is_read_only() -> None:
    if not SERVER.is_dir():
        return

    violations: list[str] = []
    for py_file in SERVER.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for method in WRITE_METHODS:
            if method in content:
                violations.append(f"{py_file}: defines {method} (HTTP write method)")

    assert not violations, (
        f"Server write method violation: {len(violations)} write handler(s) found:\n"
        + "\n".join(violations)
    )
