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

  function init() {
    var navLinks = document.querySelectorAll("nav a[data-route]");
    for (var i = 0; i < navLinks.length; i++) {
      navLinks[i].addEventListener("click", function (e) {
        e.preventDefault();
        clearError();
        showView(this.getAttribute("data-route"));
      });
    }
    showView("overview");
  }

  document.addEventListener("DOMContentLoaded", init);

  return {
    fetchJSON: fetchJSON,
    renderError: renderError,
    clearError: clearError,
    showView: showView,
  };
})();
