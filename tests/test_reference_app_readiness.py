from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = str(REPO / "scripts")


def _import_check() -> object:
    if SCRIPTS not in sys.path:
        sys.path.insert(0, SCRIPTS)
    if "check_reference_apps" in sys.modules:
        return sys.modules["check_reference_apps"]
    import check_reference_apps

    return check_reference_apps


class TestReferenceAppReadinessSuccess:
    def test_main_returns_zero_with_present_fixture(self) -> None:
        check = _import_check()
        rc = check.main()
        assert rc == 0


class TestReferenceAppReadinessFailure:
    def test_main_fails_when_fixture_missing(self) -> None:
        fixture = (
            REPO
            / "examples"
            / "reference_apps"
            / "fixtures"
            / "clarify_timeline_v0.json"
        )
        original_is_file = Path.is_file

        def fake_is_file(self: Path) -> bool:
            if self == fixture:
                return False
            return original_is_file(self)

        check = _import_check()
        with patch.object(Path, "is_file", fake_is_file):
            rc = check.main()
        assert rc == 1

    def test_main_fails_when_contract_module_missing(self) -> None:
        contract = (
            REPO / "src" / "ailuros" / "adapters" / "clarify_timeline_contract.py"
        )
        original_is_file = Path.is_file

        def fake_is_file(self: Path) -> bool:
            if self == contract:
                return False
            return original_is_file(self)

        check = _import_check()
        with patch.object(Path, "is_file", fake_is_file):
            rc = check.main()
        assert rc == 1
