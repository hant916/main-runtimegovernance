"""Import boundary tests to prevent module/package collisions."""

from __future__ import annotations

import importlib
import pathlib


def test_ailuros_regression_resolves_to_package():
    """ailuros.regression must resolve to the package, not a shadow module."""
    mod = importlib.import_module("ailuros.regression")
    init_path = pathlib.Path(mod.__file__).resolve()
    assert init_path.name == "__init__.py", (
        f"ailuros.regression.__file__ should be __init__.py, got {init_path}"
    )
    assert "regression" in init_path.parts, (
        f"ailuros.regression should be inside a regression/ package dir, got {init_path}"
    )


def test_no_shadow_module_coexists_with_package():
    """src/ailuros/regression.py must not exist alongside src/ailuros/regression/.

    Resolved from the imported package itself, not from the process working
    directory: a cwd-relative path silently skips the guard when pytest is run
    from anywhere other than the repo root, which would make this test pass
    vacuously in exactly the CI configurations it is meant to protect.
    """
    package_dir = pathlib.Path(
        importlib.import_module("ailuros.regression").__file__
    ).resolve().parent
    assert package_dir.is_dir(), "ailuros.regression must resolve to a package dir"
    assert package_dir.name == "regression"

    shadow_file = package_dir.with_suffix(".py")
    assert not shadow_file.exists(), (
        f"shadow module {shadow_file} must not exist alongside the "
        f"{package_dir} package: Python resolves the import to the package, "
        "so the module would be unreachable dead code"
    )
