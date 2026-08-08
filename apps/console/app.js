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

  // -- Init ----------------------------------------------------------------

  function _handleHashChange() {
    clearError();
    var hash = window.location.hash;
    // #runs/run_id -> run detail
    var detailMatch = hash.match(/^#runs\/(.+)$/);
    if (detailMatch) {
      navigateToRunDetail(detailMatch[1]);
      return;
    }
    // #runs -> runs list
    if (hash === "#runs") {
      loadRuns();
      return;
    }
    if (hash === "#problems") {
      showView("problems");
      return;
    }
    showView("overview");
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

    window.addEventListener("hashchange", _handleHashChange);
    if (window.location.hash) {
      _handleHashChange();
    } else {
      showView("overview");
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
  };
})();