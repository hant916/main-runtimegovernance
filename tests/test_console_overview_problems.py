from __future__ import annotations

from pathlib import Path

CONSOLE_DIR = Path(__file__).resolve().parents[1] / "apps" / "console"


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# -- API endpoint strings in app.js -----------------------------------------

def test_app_js_has_overview_endpoint() -> None:
    js = _read_file(CONSOLE_DIR / "app.js")
    assert "analytics/overview" in js, "app.js must reference /analytics/overview endpoint"


def test_app_js_has_problems_endpoint() -> None:
    js = _read_file(CONSOLE_DIR / "app.js")
    assert '"problems"' in js or "'problems'" in js, "app.js must reference /problems endpoint"


# -- HTML view elements -----------------------------------------------------

def test_index_html_has_overview_view() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert 'id="view-overview"' in html, "index.html must have overview view"


def test_index_html_has_problems_view() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert 'id="view-problems"' in html, "index.html must have problems view"


def test_index_html_has_problem_detail_view() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert 'id="view-problem-detail"' in html, "index.html must have problem detail view"


# -- Overview elements ------------------------------------------------------

def test_index_html_has_overview_filters() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert 'id="overview-start"' in html, "index.html must have overview start filter"
    assert 'id="overview-end"' in html, "index.html must have overview end filter"
    assert 'id="overview-source"' in html, "index.html must have overview source filter"
    assert 'id="overview-refresh"' in html, "index.html must have overview refresh button"


def test_index_html_has_problems_filters() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert 'id="problems-start"' in html, "index.html must have problems start filter"
    assert 'id="problems-end"' in html, "index.html must have problems end filter"
    assert 'id="problems-source"' in html, "index.html must have problems source filter"
    assert 'id="problems-refresh"' in html, "index.html must have problems refresh button"


# -- Loading / empty / error states -----------------------------------------

def test_index_html_has_overview_states() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert 'id="overview-loading"' in html, "index.html must have overview loading state"
    assert 'id="overview-error"' in html, "index.html must have overview error state"
    assert 'id="overview-empty"' in html, "index.html must have overview empty state"


def test_index_html_has_problems_states() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert 'id="problems-loading"' in html, "index.html must have problems loading state"
    assert 'id="problems-error"' in html, "index.html must have problems error state"
    assert 'id="problems-empty"' in html, "index.html must have problems empty state"


def test_index_html_has_problem_detail_states() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert 'id="pd-loading"' in html, "index.html must have problem detail loading state"
    assert 'id="pd-error"' in html, "index.html must have problem detail error state"
    assert 'id="pd-content"' in html, "index.html must have problem detail content container"


# -- Overview metric rendering -----------------------------------------------

def test_app_js_has_overview_card_rendering() -> None:
    js = _read_file(CONSOLE_DIR / "app.js")
    assert "renderOverviewCards" in js or "_renderOverviewCards" in js or "total_runs" in js, (
        "app.js must render overview metrics"
    )


def test_app_js_references_fallback_metrics() -> None:
    js = _read_file(CONSOLE_DIR / "app.js")
    assert "fallback_count" in js or "fallback_rate" in js, (
        "app.js must reference fallback metrics from FleetOverview"
    )


# -- JS functions exposure ---------------------------------------------------

def test_app_js_exposes_load_overview() -> None:
    js = _read_file(CONSOLE_DIR / "app.js")
    assert "loadOverview" in js, "app.js must expose loadOverview function"


def test_app_js_exposes_load_problems() -> None:
    js = _read_file(CONSOLE_DIR / "app.js")
    assert "loadProblems" in js, "app.js must expose loadProblems function"


def test_app_js_exposes_navigate_to_problem_detail() -> None:
    js = _read_file(CONSOLE_DIR / "app.js")
    assert "navigateToProblemDetail" in js, "app.js must expose navigateToProblemDetail function"


# -- Problem detail content sections -----------------------------------------

def test_index_html_has_problem_detail_sections() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert 'id="pd-summary-dl"' in html, "problem detail must have summary section"
    assert 'id="pd-signals-table"' in html, "problem detail must have contributing signals table"
    assert 'id="pd-affected-list"' in html, "problem detail must have affected runs list"


def test_index_html_has_problem_detail_trend() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert "Daily Trend" in html, "problem detail must have trend section"
    assert "Contributing Signals" in html, "problem detail must have contributing signals section"
    assert "Affected Runs" in html, "problem detail must have affected runs section"


def test_index_html_has_problem_detail_back_link() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    assert "Back to Problems" in html, "problem detail must have back navigation to problems"


# -- Run links in problem detail ---------------------------------------------

def test_app_js_renders_run_links_in_problem_detail() -> None:
    js = _read_file(CONSOLE_DIR / "app.js")
    assert 'href="#runs/' in js, "app.js must render run links in problem detail"


# -- Evidence refs in problem detail -----------------------------------------

def test_app_js_renders_evidence_refs_in_problem_detail() -> None:
    js = _read_file(CONSOLE_DIR / "app.js")
    assert "_renderEvidenceRefs(s.evidence_refs)" in js or "_renderEvidenceRefs(s" in js, (
        "app.js must render evidence refs in problem detail"
    )


# -- Routing for problem detail ----------------------------------------------

def test_app_js_has_problem_detail_hash_routing() -> None:
    js = _read_file(CONSOLE_DIR / "app.js")
    assert "#problems/" in js, "app.js must route #problems/{type}/{subject} to problem detail"


# -- Filter button wiring ----------------------------------------------------

def test_app_js_wires_filter_refresh_buttons() -> None:
    js = _read_file(CONSOLE_DIR / "app.js")
    assert '"overview-refresh"' in js or "overview-refresh" in js, (
        "app.js must wire overview refresh button"
    )
    assert '"problems-refresh"' in js or "problems-refresh" in js, (
        "app.js must wire problems refresh button"
    )


# -- T4: Red lines - no governance score labels -----------------------------

def test_no_governance_score_labels() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    js = _read_file(CONSOLE_DIR / "app.js")
    combined = (html + js).lower()
    forbidden = [
        "governance-score",
        "governance_score",
        "composite_score",
        "composite-score",
        "governancescore",
    ]
    for term in forbidden:
        assert term not in combined, f"Must not contain governance score term: {term}"


# -- T4: Red lines - no model-quality wording for fallback metrics -----------

def test_no_model_quality_wording_for_fallback() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    js = _read_file(CONSOLE_DIR / "app.js")
    combined = (html + js).lower()
    forbidden = [
        "model.quality",
        "model-quality",
        "model_quality",
        "modelquality",
    ]
    for term in forbidden:
        assert term not in combined, f"Must not contain model-quality wording: {term}"


# -- T4: Red lines - no AI diagnosis placeholder presented as fact ----------

def test_no_ai_diagnosis_as_fact() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    js = _read_file(CONSOLE_DIR / "app.js")
    combined = (html + js).lower()
    forbidden = [
        "ai diagnosis",
        "ai_diagnosis",
        "aidiagnosis",
        "ai.recommendation",
        "ai-recommendation",
        "llm diagnosis",
        "llm_diagnosis",
    ]
    for term in forbidden:
        assert term not in combined, f"Must not contain AI diagnosis term: {term}"


# -- T4: Red lines - no BLOCKED / HUMAN_REVIEW new paths --------------------

def test_no_blocked_or_human_review_paths() -> None:
    js = _read_file(CONSOLE_DIR / "app.js")
    assert "BLOCKED" not in js, "app.js must not introduce BLOCKED status path"
    assert "HUMAN_REVIEW" not in js, "app.js must not introduce HUMAN_REVIEW status path"


# -- T4: Red lines - no client-side aggregation over raw evidence ------------

def test_no_client_side_aggregation_over_raw_evidence() -> None:
    js = _read_file(CONSOLE_DIR / "app.js")
    forbidden = [
        "aggregate_signals",
        "compute_score",
        "derive_governance",
        "signal_aggregation",
        "compute_risk",
        "calculate_threshold",
    ]
    for term in forbidden:
        assert term not in js, f"app.js must not contain client-side aggregation: {term}"


# -- Filter helper function --------------------------------------------------

def test_app_js_has_filter_helper() -> None:
    js = _read_file(CONSOLE_DIR / "app.js")
    assert "appendFilterParams" in js or "_appendFilterParams" in js, (
        "app.js must have filter parameter helper"
    )


# -- Problem table columns ---------------------------------------------------

def test_index_html_problems_table_has_proper_columns() -> None:
    html = _read_file(CONSOLE_DIR / "index.html")
    after_problems = html.split('id="view-problems"')[1]
    if 'id="view-problem-detail"' in html:
        problems_section = after_problems.split('id="view-problem-detail"')[0]
    else:
        problems_section = after_problems
    assert "Signal Type" in problems_section, "problems table must have Signal Type column"
    assert "First Seen" in problems_section, "problems table must have First Seen column"
    assert "Last Seen" in problems_section, "problems table must have Last Seen column"
    assert "Severity" in problems_section, "problems table must have Severity column"


# -- Existing run tests not broken -------------------------------------------

def test_run_view_features_intact() -> None:
    """Verify that run detail features used by test_console_runs_view.py remain intact."""
    html = _read_file(CONSOLE_DIR / "index.html")
    assert 'id="view-run-detail"' in html, "run detail view must remain intact"
    assert "Back to Runs" in html, "run detail back-link must remain intact"

    js = _read_file(CONSOLE_DIR / "app.js")
    assert "loadRuns" in js, "loadRuns must remain intact"
    assert "navigateToRunDetail" in js, "navigateToRunDetail must remain intact"
    assert "renderError" in js, "renderError must remain intact"
