"""v0.3.0 release acceptance tests."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def test_release_smoke_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_release_v030.py")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"check_release_v030.py failed (exit {result.returncode}):\n"
        f"{result.stdout}\n{result.stderr}"
    )


def test_release_acceptance_doc_exists() -> None:
    doc = ROOT / "docs" / "release" / "v0.3.0-acceptance.md"
    assert doc.exists(), "docs/release/v0.3.0-acceptance.md not found"
    content = doc.read_text(encoding="utf-8")

    assert "acceptance-defined" in content
    assert "IMPLEMENTED" in content
    assert "NON-GOAL" in content
    assert "Acceptance Matrix" in content

    assert "audit package exporter" in content.lower()
    assert "refund governance demo" in content.lower()
    assert "release acceptance gate" in content.lower()


def test_release_doc_non_goals_are_explicit() -> None:
    doc = ROOT / "docs" / "release" / "v0.3.0-acceptance.md"
    content = doc.read_text(encoding="utf-8")

    assert "UI dashboard" in content
    assert "server write API" in content
    assert "production integrations" in content
    assert "broad adapter ecosystem" in content
    assert "agent orchestration" in content
    assert "MCP Gateway" in content


def test_audit_package_contract_marker_present() -> None:
    ap = ROOT / "src" / "ailuros" / "audit_package.py"
    assert ap.exists()
    content = ap.read_text(encoding="utf-8")
    assert "export_audit_package_to_dir" in content
    assert "ailuros.audit-package.v1" in content


def test_refund_demo_has_no_network_dependency() -> None:
    demo = ROOT / "examples" / "refund_governance_demo.py"
    assert demo.exists()
    content = demo.read_text(encoding="utf-8")
    forbidden_imports = [
        "import urllib",
        "import requests",
        "import httpx",
        "import aiohttp",
        "import socket",
        "from urllib",
        "from requests",
        "import http.client",
    ]
    for fi in forbidden_imports:
        assert fi not in content, (
            f"refund_governance_demo.py should not contain {fi}"
        )


def test_v020_prerequisite_files_exist() -> None:
    assert (ROOT / "docs" / "release" / "v0.2.0-acceptance.md").exists()
    assert (ROOT / "scripts" / "check_release_v020.py").exists()


def test_v030_scope_doc_exists() -> None:
    scope = ROOT / "docs" / "release" / "v0.3.0-scope.md"
    assert scope.exists(), "docs/release/v0.3.0-scope.md not found"


def test_release_doc_does_not_claim_production_integrations() -> None:
    doc = ROOT / "docs" / "release" / "v0.3.0-acceptance.md"
    content = doc.read_text(encoding="utf-8")

    assert "Clarify integration" in content or "Clarify" in content
    assert "radarCreation integration" in content or "radarCreation" in content
    assert "browser governance" in content
    assert "MCP Gateway" in content
    assert "does **not** introduce" in content
