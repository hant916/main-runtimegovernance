var AilurosConsole = (function () {
  "use strict";

  function _getApiBase() {
    var params = new URLSearchParams(window.location.search);
    var query = params.get("api_base");
    if (query) return query;

    var meta = document.querySelector('meta[name="ailuros-api-base"]');
    if (meta && meta.content) return meta.content;

    return "http://localhost:8080";
  }

  function _statusLabel(status) {
    var map = {
      ok: "status-ok",
      error: "status-error",
      warning: "status-warning",
      unknown: "status-unknown",
    };
    return map[status] || "status-unknown";
  }

  function renderError(message) {
    var view = document.getElementById("view-error");
    var msg = document.getElementById("error-message");
    if (!view || !msg) return;
    msg.textContent = message || "An unexpected error occurred.";
    view.classList.remove("hidden");
  }

  function clearError() {
    var view = document.getElementById("view-error");
    if (view) view.classList.add("hidden");
  }

  function fetchJSON(path) {
    var base = _getApiBase();
    var url = base.replace(/\/+$/, "") + "/" + path.replace(/^\/+/, "");

    return fetch(url)
      .then(function (response) {
        if (!response.ok) {
          throw new Error("API unavailable: " + response.status + " " + response.statusText);
        }
        return response.json();
      })
      .catch(function (err) {
        if (err instanceof TypeError || /NetworkError|Failed to fetch/i.test(err.message)) {
          renderError("API server is unavailable. Check that the server is running at " + base + ".");
        } else {
          renderError(err.message);
        }
        throw err;
      });
  }

  function showView(name) {
    var views = document.querySelectorAll(".view");
    for (var i = 0; i < views.length; i++) {
      views[i].classList.add("hidden");
    }
    var target = document.getElementById("view-" + name);
    if (target) target.classList.remove("hidden");
  }

  // -- Helpers -------------------------------------------------------------

  function _getDefaultWindow() {
    var end = new Date();
    var start = new Date(end.getTime() - 7 * 24 * 60 * 60 * 1000);
    return { start: start.toISOString(), end: end.toISOString() };
  }

  function _appendFilterParams(basePath, startElId, endElId, sourceElId) {
    var startEl = document.getElementById(startElId);
    var endEl = document.getElementById(endElId);
    var sourceEl = document.getElementById(sourceElId);
    var params = [];
    if (startEl && startEl.value) {
      params.push("window_start=" + encodeURIComponent(startEl.value));
    }
    if (endEl && endEl.value) {
      params.push("window_end=" + encodeURIComponent(endEl.value));
    }
    if (sourceEl && sourceEl.value) {
      params.push("source=" + encodeURIComponent(sourceEl.value));
    }
    if (params.length) {
      return basePath + "?" + params.join("&");
    }
    return basePath;
  }

  // -- Runs list -----------------------------------------------------------

  function _escapeHTML(str) {
    var div = document.createElement("div");
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  function _formatTime(isoStr) {
    if (!isoStr) return "";
    var d = new Date(isoStr);
    if (isNaN(d.getTime())) return _escapeHTML(isoStr);
    return d.toLocaleString();
  }

  function loadRuns() {
    clearError();
    showView("runs");

    var loading = document.getElementById("runs-loading");
    var empty = document.getElementById("runs-empty");
    var tbody = document.querySelector("#runs-table tbody");
    if (tbody) tbody.innerHTML = "";
    if (loading) loading.classList.remove("hidden");
    if (empty) empty.classList.add("hidden");

    fetchJSON("runs")
      .then(function (runs) {
        if (loading) loading.classList.add("hidden");
        if (!runs || runs.length === 0) {
          if (empty) empty.classList.remove("hidden");
          return;
        }
        if (empty) empty.classList.add("hidden");

        var rows = "";
        for (var i = 0; i < runs.length; i++) {
          var r = runs[i];
          rows += '<tr class="clickable-row" data-run-id="' + _escapeHTML(r.run_id) + '">' +
            '<td>' + _escapeHTML(r.run_id) + '</td>' +
            '<td>' + _escapeHTML(r.agent_id || "") + '</td>' +
            '<td><span class="status-' + _escapeHTML(r.status || "unknown") + '">' + _escapeHTML(r.status || "unknown") + '</span></td>' +
            '<td>' + _formatTime(r.created_at) + '</td>' +
            '</tr>';
        }
        if (tbody) tbody.innerHTML = rows;

        var rowsEls = tbody ? tbody.querySelectorAll("tr[data-run-id]") : [];
        for (var j = 0; j < rowsEls.length; j++) {
          rowsEls[j].addEventListener("click", function () {
            var rid = this.getAttribute("data-run-id");
            if (rid) navigateToRunDetail(rid);
          });
        }
      })
      .catch(function () {
        if (loading) loading.classList.add("hidden");
      });
  }

  // -- Overview -------------------------------------------------------------

  function loadOverview() {
    clearError();
    showView("overview");

    var w = _getDefaultWindow();
    var startEl = document.getElementById("overview-start");
    var endEl = document.getElementById("overview-end");
    if (startEl && !startEl.value) startEl.value = w.start;
    if (endEl && !endEl.value) endEl.value = w.end;

    var loading = document.getElementById("overview-loading");
    var errorEl = document.getElementById("overview-error");
    var empty = document.getElementById("overview-empty");
    var cards = document.getElementById("overview-cards");
    if (loading) loading.classList.remove("hidden");
    if (errorEl) errorEl.classList.add("hidden");
    if (empty) empty.classList.add("hidden");
    if (cards) cards.innerHTML = "";

    var path = _appendFilterParams("analytics/overview", "overview-start", "overview-end", "overview-source");
    fetchJSON(path)
      .then(function (data) {
        if (loading) loading.classList.add("hidden");
        if (!data || data.total_runs === 0) {
          if (empty) empty.classList.remove("hidden");
          if (cards) cards.innerHTML = "";
          return;
        }
        if (empty) empty.classList.add("hidden");
        _renderOverviewCards(data);
      })
      .catch(function (err) {
        if (loading) loading.classList.add("hidden");
        if (errorEl) {
          errorEl.textContent = err.message || "Failed to load overview.";
          errorEl.classList.remove("hidden");
        }
      });
  }

  function _renderOverviewCards(data) {
    var cards = document.getElementById("overview-cards");
    if (!cards) return;

    var total = data.total_runs;
    var html = "";

    html += _renderMetricCard("Total Runs", String(total), "Total runs in window");

    var outcomes = data.outcomes || {};
    var outcomeKeys = Object.keys(outcomes);
    for (var oi = 0; oi < outcomeKeys.length; oi++) {
      var ok = outcomeKeys[oi];
      html += _renderMetricCard("Outcome: " + _escapeHTML(ok), String(outcomes[ok]) + " / " + String(total), "");
    }

    var validations = data.validations || {};
    var valKeys = Object.keys(validations);
    for (var vi = 0; vi < valKeys.length; vi++) {
      var vk = valKeys[vi];
      html += _renderMetricCard("Validation: " + _escapeHTML(vk), String(validations[vk]) + " / " + String(total), "");
    }

    var scopes = data.scopes || {};
    var scopeKeys = Object.keys(scopes);
    for (var si = 0; si < scopeKeys.length; si++) {
      var sk = scopeKeys[si];
      html += _renderMetricCard("Scope: " + _escapeHTML(sk), String(scopes[sk]) + " / " + String(total), "");
    }

    if (data.fallback_count != null) {
      html += _renderMetricCard("Fallback Events", String(data.fallback_count) + " (" + (data.fallback_rate != null ? (Math.round(data.fallback_rate * 1000) / 10).toString() + "%" : "0%") + ")", "Runs using fallback paths");
    }

    var signals = data.signals || {};
    var signalKeys = Object.keys(signals);
    for (var gsi = 0; gsi < signalKeys.length; gsi++) {
      var gsk = signalKeys[gsi];
      html += _renderMetricCard("Signal: " + _escapeHTML(gsk), String(signals[gsk]), "");
    }

    var sources = data.sources || {};
    var srcKeys = Object.keys(sources);
    for (var sri = 0; sri < srcKeys.length; sri++) {
      var srk = srcKeys[sri];
      html += _renderMetricCard("Source: " + _escapeHTML(srk), String(sources[srk]), "");
    }

    cards.innerHTML = html;
  }

  function _renderMetricCard(label, value, description) {
    var desc = description ? '<p class="card-desc">' + _escapeHTML(description) + '</p>' : "";
    return '<div class="card">' +
      '<h3>' + _escapeHTML(label) + '</h3>' +
      '<div class="value">' + _escapeHTML(value) + '</div>' +
      desc +
      '</div>';
  }

  // -- Run Detail ----------------------------------------------------------

  function navigateToRunDetail(runId) {
    clearError();
    showView("run-detail");

    var loading = document.getElementById("run-detail-loading");
    var errorEl = document.getElementById("run-detail-error");
    var content = document.getElementById("run-detail-content");
    if (loading) loading.classList.remove("hidden");
    if (errorEl) errorEl.classList.add("hidden");
    if (content) content.classList.add("hidden");

    _renderRunDetail(runId);
  }

  function _renderRunDetail(runId) {
    var reportPath = "runs/" + encodeURIComponent(runId) + "/report";
    var signalsPath = "runs/" + encodeURIComponent(runId) + "/signals";

    var loading = document.getElementById("run-detail-loading");
    var errorEl = document.getElementById("run-detail-error");
    var content = document.getElementById("run-detail-content");

    Promise.all([fetchJSON(reportPath), fetchJSON(signalsPath)])
      .then(function (results) {
        var report = results[0];
        var signals = results[1];
        if (loading) loading.classList.add("hidden");
        _populateRunDetail(report, signals);
        if (content) content.classList.remove("hidden");
      })
      .catch(function (err) {
        if (loading) loading.classList.add("hidden");
        if (errorEl) {
          errorEl.textContent = err.message || "Failed to load run detail.";
          errorEl.classList.remove("hidden");
        }
      });
  }

  function _populateBasics(report) {
    var dl = document.getElementById("rd-basics-dl");
    if (!dl) return;
    var items = [
      ["Run ID", report.run_id || ""],
      ["Lifecycle", report.lifecycle || ""],
      ["Outcome", report.outcome || ""],
      ["Validation", report.validation || ""],
      ["Scope", report.scope || ""],
      ["Why Stopped", report.why_stopped || ""],
      ["Steps", String(report.step_count != null ? report.step_count : "")],
      ["Decisions", String(report.decision_count != null ? report.decision_count : "")],
      ["Events", String(report.event_count != null ? report.event_count : "")],
      ["Started", _formatTime(report.started_at)],
      ["Completed", _formatTime(report.completed_at)],
    ];
    var html = "";
    for (var i = 0; i < items.length; i++) {
      html += "<dt>" + _escapeHTML(items[i][0]) + "</dt>" +
        "<dd>" + _escapeHTML(items[i][1]) + "</dd>";
    }
    dl.innerHTML = html;
  }

  function _renderSignalCard(sig) {
    var refsHTML = _renderEvidenceRefs(sig.evidence_refs);
    return '<div class="signal-card">' +
      '<div class="signal-header">' +
      '<span class="signal-type">' + _escapeHTML(sig.type) + '</span>' +
      '<span class="signal-severity severity-' + _escapeHTML(sig.severity) + '">' + _escapeHTML(sig.severity) + '</span>' +
      '</div>' +
      '<div class="signal-subject">' + _escapeHTML(sig.subject) + '</div>' +
      refsHTML +
      '</div>';
  }

  function _populateSignals(signals) {
    var empty = document.getElementById("rd-signals-empty");
    var listEl = document.getElementById("rd-signals-list");
    if (!listEl) return;
    if (!signals || signals.length === 0) {
      if (empty) empty.classList.remove("hidden");
      listEl.innerHTML = "";
      return;
    }
    if (empty) empty.classList.add("hidden");
    var html = "";
    for (var i = 0; i < signals.length; i++) {
      html += _renderSignalCard(signals[i]);
    }
    listEl.innerHTML = html;
  }

  function _populateStringList(elId, emptyId, items) {
    var listEl = document.getElementById(elId);
    var empty = document.getElementById(emptyId);
    if (!listEl) return;
    if (!items || items.length === 0) {
      if (empty) empty.classList.remove("hidden");
      listEl.innerHTML = "";
      return;
    }
    if (empty) empty.classList.add("hidden");
    var html = "";
    for (var i = 0; i < items.length; i++) {
      html += "<li>" + _escapeHTML(typeof items[i] === "string" ? items[i] : items[i].description || JSON.stringify(items[i])) + "</li>";
    }
    listEl.innerHTML = html;
  }

  function _populateRunDetail(report, signals) {
    _populateBasics(report);
    _populateSignals(signals);
    _populateStringList("rd-decisions-list", "rd-decisions-empty", report.decision_reasons);
    _populateStringList("rd-changes-list", "rd-changes-empty", report.changes);
    _renderEvidenceRefsSection(report.evidence_refs);
  }

  // -- Evidence Refs -------------------------------------------------------

  function _renderEvidenceRefs(refs) {
    if (!refs || refs.length === 0) return "";
    var html = '<ul class="evidence-refs">';
    for (var i = 0; i < refs.length; i++) {
      var r = refs[i];
      var parts = [];
      if (r.event_id) parts.push("event:" + _escapeHTML(r.event_id));
      if (r.artifact) parts.push("artifact:" + _escapeHTML(r.artifact));
      if (r.pointer) parts.push("pointer:" + _escapeHTML(r.pointer));
      html += "<li>" + parts.join(" ") + "</li>";
    }
    html += "</ul>";
    return html;
  }

  function _renderEvidenceRefsSection(refs) {
    var empty = document.getElementById("rd-evidence-empty");
    var listEl = document.getElementById("rd-evidence-list");
    if (!listEl) return;
    if (!refs || refs.length === 0) {
      if (empty) empty.classList.remove("hidden");
      listEl.innerHTML = "";
      return;
    }
    if (empty) empty.classList.add("hidden");
    listEl.innerHTML = _renderEvidenceRefs(refs);
  }

  // -- Problems list --------------------------------------------------------

  function loadProblems() {
    clearError();
    showView("problems");

    var loading = document.getElementById("problems-loading");
    var errorEl = document.getElementById("problems-error");
    var empty = document.getElementById("problems-empty");
    var tbody = document.querySelector("#problems-table tbody");
    if (tbody) tbody.innerHTML = "";
    if (loading) loading.classList.remove("hidden");
    if (errorEl) errorEl.classList.add("hidden");
    if (empty) empty.classList.add("hidden");

    var path = _appendFilterParams("problems", "problems-start", "problems-end", "problems-source");
    fetchJSON(path)
      .then(function (groups) {
        if (loading) loading.classList.add("hidden");
        if (!groups || groups.length === 0) {
          if (empty) empty.classList.remove("hidden");
          if (tbody) tbody.innerHTML = "";
          return;
        }
        if (empty) empty.classList.add("hidden");
        _renderProblemsTable(groups);
      })
      .catch(function (err) {
        if (loading) loading.classList.add("hidden");
        if (errorEl) {
          errorEl.textContent = err.message || "Failed to load problems.";
          errorEl.classList.remove("hidden");
        }
      });
  }

  function _renderProblemsTable(groups) {
    var tbody = document.querySelector("#problems-table tbody");
    if (!tbody) return;

    var html = "";
    for (var i = 0; i < groups.length; i++) {
      var g = groups[i];
      var severityParts = [];
      var sev = g.severity_counts || {};
      var sevKeys = Object.keys(sev);
      for (var si = 0; si < sevKeys.length; si++) {
        severityParts.push(_escapeHTML(sevKeys[si]) + ":" + String(sev[sevKeys[si]]));
      }
      var key = encodeURIComponent(g.signal_type) + "/" + encodeURIComponent(g.subject_key);
      html += '<tr class="clickable-row" data-problem-key="' + _escapeHTML(key) + '">' +
        '<td>' + _escapeHTML(g.signal_type) + '</td>' +
        '<td>' + _escapeHTML(g.subject_key) + '</td>' +
        '<td>' + String(g.count) + '</td>' +
        '<td>' + _formatTime(g.first_seen) + '</td>' +
        '<td>' + _formatTime(g.last_seen) + '</td>' +
        '<td>' + severityParts.join(" ") + '</td>' +
        '</tr>';
    }
    tbody.innerHTML = html;

    var rows = tbody.querySelectorAll("tr[data-problem-key]");
    for (var j = 0; j < rows.length; j++) {
      rows[j].addEventListener("click", function () {
        var key = this.getAttribute("data-problem-key");
        if (key) {
          var parts = key.split("/");
          if (parts.length >= 2) {
            navigateToProblemDetail(decodeURIComponent(parts[0]), decodeURIComponent(parts[1]));
          }
        }
      });
    }
  }

  // -- Problem detail -------------------------------------------------------

  function navigateToProblemDetail(signalType, subjectKey) {
    clearError();
    showView("problem-detail");

    var loading = document.getElementById("pd-loading");
    var errorEl = document.getElementById("pd-error");
    var content = document.getElementById("pd-content");
    if (loading) loading.classList.remove("hidden");
    if (errorEl) errorEl.classList.add("hidden");
    if (content) content.classList.add("hidden");

    var path = "problems/" + encodeURIComponent(signalType) + "/" + encodeURIComponent(subjectKey);

    fetchJSON(path)
      .then(function (data) {
        if (loading) loading.classList.add("hidden");
        _renderProblemDetail(data);
        if (content) content.classList.remove("hidden");
      })
      .catch(function (err) {
        if (loading) loading.classList.add("hidden");
        if (errorEl) {
          errorEl.textContent = err.message || "Failed to load problem detail.";
          errorEl.classList.remove("hidden");
        }
      });

  }

  function _renderProblemDetail(data) {
    var group = data.group || {};
    var signals = data.contributing_signals || [];

    var dl = document.getElementById("pd-summary-dl");
    if (dl) {
      var items = [
        ["Signal Type", data.signal_type || ""],
        ["Subject", data.subject_key || ""],
        ["Total Occurrences", String(group.count != null ? group.count : signals.length)],
        ["First Seen", _formatTime(group.first_seen)],
        ["Last Seen", _formatTime(group.last_seen)],
      ];
      var severityCounts = group.severity_counts || {};
      var sevKeys2 = Object.keys(severityCounts);
      for (var si2 = 0; si2 < sevKeys2.length; si2++) {
        items.push(["Severity: " + _escapeHTML(sevKeys2[si2]), String(severityCounts[sevKeys2[si2]])]);
      }
      var html = "";
      for (var dli = 0; dli < items.length; dli++) {
        html += "<dt>" + _escapeHTML(items[dli][0]) + "</dt><dd>" + _escapeHTML(items[dli][1]) + "</dd>";
      }
      dl.innerHTML = html;
    }

    var trendBucks = group.trend_buckets || [];
    var trendEmpty = document.getElementById("pd-trend-empty");
    var trendTbody = document.querySelector("#pd-trend-table tbody");
    if (trendTbody) {
      if (trendBucks.length === 0) {
        if (trendEmpty) trendEmpty.classList.remove("hidden");
        trendTbody.innerHTML = "";
      } else {
        if (trendEmpty) trendEmpty.classList.add("hidden");
        var trendHtml = "";
        for (var ti = 0; ti < trendBucks.length; ti++) {
          trendHtml += "<tr><td>" + _escapeHTML(trendBucks[ti].label) + "</td><td>" + String(trendBucks[ti].count) + "</td></tr>";
        }
        trendTbody.innerHTML = trendHtml;
      }
    }

    var sigsEmpty = document.getElementById("pd-signals-empty");
    var sigsTbody = document.querySelector("#pd-signals-table tbody");
    if (sigsTbody) {
      if (!signals || signals.length === 0) {
        if (sigsEmpty) sigsEmpty.classList.remove("hidden");
        sigsTbody.innerHTML = "";
      } else {
        if (sigsEmpty) sigsEmpty.classList.add("hidden");
        var sigsHtml = "";
        for (var sgi = 0; sgi < signals.length; sgi++) {
          var s = signals[sgi];
          var evHtml = _renderEvidenceRefs(s.evidence_refs);
          sigsHtml += '<tr>' +
            '<td>' + _escapeHTML(s.signal_id) + '</td>' +
            '<td><a href="#runs/' + encodeURIComponent(s.run_id) + '" class="run-link">' + _escapeHTML(s.run_id) + '</a></td>' +
            '<td><span class="signal-severity severity-' + _escapeHTML(s.severity) + '">' + _escapeHTML(s.severity) + '</span></td>' +
            '<td>' + evHtml + '</td>' +
            '<td>' + _formatTime(s.created_at) + '</td>' +
            '</tr>';
        }
        sigsTbody.innerHTML = sigsHtml;

        var runLinks = sigsTbody.querySelectorAll("a.run-link");
        for (var rli = 0; rli < runLinks.length; rli++) {
          runLinks[rli].addEventListener("click", function (e) {
            e.preventDefault();
            var href = this.getAttribute("href");
            if (href) window.location.hash = href;
          });
        }
      }
    }

    var affectedIds = group.affected_run_ids || [];
    var affectedEmpty = document.getElementById("pd-affected-empty");
    var affectedList = document.getElementById("pd-affected-list");
    if (affectedList) {
      if (affectedIds.length === 0) {
        if (affectedEmpty) affectedEmpty.classList.remove("hidden");
        affectedList.innerHTML = "";
      } else {
        if (affectedEmpty) affectedEmpty.classList.add("hidden");
        var affHtml = "";
        for (var ai = 0; ai < affectedIds.length; ai++) {
          affHtml += '<li><a href="#runs/' + encodeURIComponent(affectedIds[ai]) + '" class="run-link">' + _escapeHTML(affectedIds[ai]) + '</a></li>';
        }
        affectedList.innerHTML = affHtml;
        var affLinks = affectedList.querySelectorAll("a.run-link");
        for (var ali = 0; ali < affLinks.length; ali++) {
          affLinks[ali].addEventListener("click", function (e) {
            e.preventDefault();
            var href = this.getAttribute("href");
            if (href) window.location.hash = href;
          });
        }
      }
    }
  }

  // -- Init ----------------------------------------------------------------

  function _handleHashChange() {
    clearError();
    var hash = window.location.hash;
    // #runs/run_id -> run detail
    var runDetailMatch = hash.match(/^#runs\/(.+)$/);
    if (runDetailMatch) {
      navigateToRunDetail(runDetailMatch[1]);
      return;
    }
    // #problems/{signal_type}/{subject_key} -> problem detail
    var problemDetailMatch = hash.match(/^#problems\/(.+)\/(.+)$/);
    if (problemDetailMatch) {
      navigateToProblemDetail(
        decodeURIComponent(problemDetailMatch[1]),
        decodeURIComponent(problemDetailMatch[2])
      );
      return;
    }
    // #runs -> runs list
    if (hash === "#runs") {
      loadRuns();
      return;
    }
    if (hash === "#problems") {
      loadProblems();
      return;
    }
    loadOverview();
  }

  function init() {
    var navLinks = document.querySelectorAll("nav a[data-route]");
    for (var i = 0; i < navLinks.length; i++) {
      navLinks[i].addEventListener("click", function (e) {
        e.preventDefault();
        clearError();
        var route = this.getAttribute("data-route");
        window.location.hash = route;
      });
    }

    // back-link clicks
    var backLinks = document.querySelectorAll(".back-link[data-route]");
    for (var j = 0; j < backLinks.length; j++) {
      backLinks[j].addEventListener("click", function (e) {
        e.preventDefault();
        clearError();
        var route = this.getAttribute("data-route");
        window.location.hash = route;
      });
    }

    // filter refresh buttons
    var ovRefresh = document.getElementById("overview-refresh");
    if (ovRefresh) {
      ovRefresh.addEventListener("click", function () {
        loadOverview();
      });
    }
    var prRefresh = document.getElementById("problems-refresh");
    if (prRefresh) {
      prRefresh.addEventListener("click", function () {
        loadProblems();
      });
    }

    window.addEventListener("hashchange", _handleHashChange);
    if (window.location.hash) {
      _handleHashChange();
    } else {
      loadOverview();
    }
  }

  document.addEventListener("DOMContentLoaded", init);

  return {
    fetchJSON: fetchJSON,
    renderError: renderError,
    clearError: clearError,
    showView: showView,
    loadRuns: loadRuns,
    navigateToRunDetail: navigateToRunDetail,
    loadOverview: loadOverview,
    loadProblems: loadProblems,
    navigateToProblemDetail: navigateToProblemDetail,
  };
})();