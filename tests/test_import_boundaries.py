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
    """src/ailuros/regression.py must not exist alongside src/ailuros/regression/."""
    package_dir = pathlib.Path("src/ailuros/regression")
    shadow_file = pathlib.Path("src/ailuros/regression.py")
    if package_dir.is_dir():
        assert not shadow_file.exists(), (
            "src/ailuros/regression.py shadow module must not exist "
            "when src/ailuros/regression/ package is present"
        )
