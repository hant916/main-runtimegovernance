from __future__ import annotations

from pathlib import Path

CONSOLE_DIR = Path(__file__).resolve().parents[1] / "apps" / "console"
REQUIRED_FILES = ["index.html", "app.js", "styles.css"]
FORBIDDEN_FILES = [
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "npm-shrinkwrap.json",
    "node_modules",
]


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_required_files_exist() -> None:
    for fname in REQUIRED_FILES:
        fpath = CONSOLE_DIR / fname
        assert fpath.is_file(), f"Missing required file: {fpath}"


def test_no_npm_manifest_or_lockfile() -> None:
    for fname in FORBIDDEN_FILES:
        fpath = CONSOLE_DIR / fname
        assert not fpath.exists(), f"Forbidden file or directory present: {fpath}"


def test_index_html_has_nav_landmark() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert "<nav" in html, "index.html is missing a <nav> element"


def test_index_html_has_main_landmark() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert "<main" in html, "index.html is missing a <main> element"


def test_index_html_has_alert_role() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert 'role="alert"' in html, "index.html is missing role=alert on error region"


def test_index_html_has_aria_live_region() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert "aria-live" in html, "index.html is missing aria-live attribute on live region"


def test_index_html_has_skip_link() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert "skip" in html.lower() and 'href="#main-content"' in html, (
        "index.html is missing a skip-to-content link"
    )


def test_index_html_has_nav_overview() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert "Overview" in html, "index.html nav is missing Overview link"


def test_index_html_has_nav_runs() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert "Runs" in html, "index.html nav is missing Runs link"


def test_index_html_has_nav_problems() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert "Problems" in html, "index.html nav is missing Problems link"


def test_app_js_exposes_fetch_json() -> None:
    js = _read_file(CONSOLE_DIR / "app.js")
    assert "fetchJSON" in js, "app.js is missing fetchJSON API helper"


def test_app_js_handles_unavailable() -> None:
    js = _read_file(CONSOLE_DIR / "app.js")
    assert "unavailable" in js.lower(), "app.js must handle unavailable API rendering"


def test_app_js_handles_error() -> None:
    js = _read_file(CONSOLE_DIR / "app.js")
    assert "renderError" in js, "app.js is missing explicit error rendering"


def test_app_js_configurable_api_base() -> None:
    js = _read_file(CONSOLE_DIR / "app.js")
    assert "api_base" in js or "_getApiBase" in js, (
        "app.js must support configurable API base"
    )


def test_styles_css_has_table_rules() -> None:
    css = _read_file(CONSOLE_DIR / "styles.css")
    assert ".data-table" in css, "styles.css is missing table styling"


def test_styles_css_has_status_labels() -> None:
    css = _read_file(CONSOLE_DIR / "styles.css")
    assert "status-ok" in css or "status-error" in css, (
        "styles.css is missing status label styles"
    )
