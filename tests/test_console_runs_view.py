from __future__ import annotations

from pathlib import Path

CONSOLE_DIR = Path(__file__).resolve().parents[1] / "apps" / "console"


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# -- API endpoint strings in app.js -----------------------------------------

def test_app_js_has_runs_endpoint() -> None:
    js = _read_file(CONSOLE_DIR / "app.js")
    assert '"runs"' in js or "'runs'" in js, "app.js must reference /runs endpoint"


def test_app_js_has_run_report_endpoint() -> None:
    js = _read_file(CONSOLE_DIR / "app.js")
    assert "/report" in js, "app.js must reference /runs/{id}/report endpoint"


def test_app_js_has_run_signals_endpoint() -> None:
    js = _read_file(CONSOLE_DIR / "app.js")
    assert "/signals" in js, "app.js must reference /runs/{id}/signals endpoint"


# -- Section labels in index.html -------------------------------------------

def test_index_html_has_run_detail_view() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert 'id="view-run-detail"' in html, "index.html must have run-detail view"


def test_index_html_has_summary_section() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert "Summary" in html, "index.html must have Summary section label"


def test_index_html_has_signals_section() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert "Signals" in html, "index.html must have Signals section label"


def test_index_html_has_decisions_section() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert "Decisions" in html, "index.html must have Decisions section label"


def test_index_html_has_changes_section() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert "Changes" in html, "index.html must have Changes section label"


def test_index_html_has_evidence_references_section() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert "Evidence References" in html, "index.html must have Evidence References section label"


def test_index_html_has_back_link() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert "Back to Runs" in html, "index.html must have back navigation to runs"


# -- Loading / empty / error states -----------------------------------------

def test_app_js_has_loading_state() -> None:
    js = _read_file(CONSOLE_DIR / "app.js")
    assert "runs-loading" in js or "Loading runs" in js, "app.js must render loading state for runs"


def test_app_js_has_empty_state() -> None:
    js = _read_file(CONSOLE_DIR / "app.js")
    assert "runs-empty" in js or "No runs" in js, "app.js must render empty state for runs"


def test_app_js_has_error_state() -> None:
    js = _read_file(CONSOLE_DIR / "app.js")
    assert "renderError" in js, "app.js must render error state"


def test_index_html_has_loading_element() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert 'id="runs-loading"' in html, "index.html must have runs loading element"


def test_index_html_has_empty_element() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert 'id="runs-empty"' in html, "index.html must have runs empty element"


# -- Run detail state elements ----------------------------------------------

def test_index_html_has_detail_loading() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert 'id="run-detail-loading"' in html, "index.html must have detail loading element"


def test_index_html_has_detail_error() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert 'id="run-detail-error"' in html, "index.html must have detail error element"


# -- Absence of client-side governance inference ---------------------------

def test_app_js_no_inference_constants() -> None:
    text = _read_file(CONSOLE_DIR / "app.js").lower()
    forbidden = ["infer_governance", "derive_decision", "governance_inference",
                 "blocked_by_policy", "human_review_trigger"]
    for term in forbidden:
        assert term not in text, f"app.js must not contain client-side inference constant: {term}"


def test_app_js_no_policy_evaluation() -> None:
    js = _read_file(CONSOLE_DIR / "app.js")
    assert "evaluate_policy" not in js, "app.js must not contain policy evaluation code"
    assert "policy_match" not in js, "app.js must not contain policy matching logic"
    assert "policyMatcher" not in js, "app.js must not contain policy matching logic"


def test_app_js_evidence_refs_safe() -> None:
    js = _read_file(CONSOLE_DIR / "app.js")
    assert "file://" not in js.lower(), "app.js must not contain file:// URL execution"
    assert "eval(" not in js, "app.js must not use eval() for evidence rendering"
