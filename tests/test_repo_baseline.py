"""Tests for the repo baseline sanity checker."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
CHECKER = SCRIPTS / "check_repo_baseline.py"


def test_checker_runs_with_exit_zero():
    result = subprocess.run(
        [sys.executable, str(CHECKER)],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    assert result.returncode == 0


def test_checker_output_contains_all_checks():
    result = subprocess.run(
        [sys.executable, str(CHECKER)],
        capture_output=True, text=True,
    )
    assert "[PASS]" in result.stdout
    assert "7/7 checks passed" in result.stdout
    assert "version is 0.3.0" in result.stdout
    assert "CHANGELOG.md" in result.stdout
    assert "hello.py exists" in result.stdout
    assert "ADR-0001" in result.stdout
    assert "ADR-0002" in result.stdout
    assert "ADR-0003" in result.stdout
    assert "roadmap.md" in result.stdout
    assert "Phase 5 deferral" in result.stdout
    assert "README references hello demo or runnable example" in result.stdout


@pytest.fixture
def import_checker():
    spec = importlib.util.spec_from_file_location("check_repo_baseline", CHECKER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_check_version_true_on_real_repo(import_checker):
    ok = import_checker.check_version()
    assert ok is True


def test_check_changelog_true_on_real_repo(import_checker):
    ok = import_checker.check_changelog()
    assert ok is True


def test_check_hello_demo_true_on_real_repo(import_checker):
    ok = import_checker.check_hello_demo()
    assert ok is True


def test_check_adr_docs_true_on_real_repo(import_checker):
    ok = import_checker.check_adr_docs()
    assert ok is True


def test_check_roadmap_true_on_real_repo(import_checker):
    ok = import_checker.check_roadmap()
    assert ok is True


def test_check_phase5_deferral_true_on_real_repo(import_checker):
    ok = import_checker.check_phase5_deferral()
    assert ok is True


def test_check_readme_refers_to_demo_true_on_real_repo(import_checker):
    ok = import_checker.check_readme_refers_to_demo()
    assert ok is True
