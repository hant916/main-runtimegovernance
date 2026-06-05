from __future__ import annotations

import re
from pathlib import Path

AILUROS = Path("src/ailuros")
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


def test_no_reference_app_terms_in_evidence_core() -> None:
    violations: list[str] = []
    for py_file in _core_py_files():
        content = py_file.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_REFERENCE_TERMS:
            if re.search(pattern, content, re.IGNORECASE):
                violations.append(f"{py_file}: matches {pattern!r}")

    assert not violations, (
        f"Evidence pipeline boundary: {len(violations)} reference-app term(s)"
        f" found in src/ailuros/ (excluding adapters/):\n"
        + "\n".join(violations)
    )


def test_no_evidence_write_routes_in_server() -> None:
    if not SERVER.is_dir():
        return

    violations: list[str] = []
    for py_file in SERVER.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for method in EVIDENCE_WRITE_METHODS:
            if method in content:
                violations.append(f"{py_file}: defines {method}")

    assert not violations, (
        f"Server write methods: {len(violations)} write handler(s) found:\n"
        + "\n".join(violations)
    )
