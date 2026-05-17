/* Smart Campus Service Desk — front-end behaviours */

function confirmDelete() {
  return confirm("Are you sure you want to delete this ticket?");
}

function confirmDeleteUser() {
  return confirm(
    "Delete this user permanently? Their tickets (if any) will be removed and assignments cleared. This cannot be undone."
  );
}

/** Admin reports page: load JSON from Flask API (session cookie). */
(function initReportDashboard() {
  const app = document.getElementById("sd-reports-app");
  if (!app) return;

  const summaryUrl = app.dataset.summaryUrl;
  const ticketsUrl = app.dataset.ticketsUrl;
  const summaryOut = document.getElementById("sd-report-summary-body");
  const ticketsOut = document.getElementById("sd-report-tickets-body");
  const statusEl = document.getElementById("sd-reports-status");
  const refreshBtn = document.getElementById("sd-reports-refresh");

  if (
    !summaryUrl ||
    !ticketsUrl ||
    !summaryOut ||
    !ticketsOut ||
    !statusEl ||
    !refreshBtn
  ) {
    return;
  }

  const statusFilterSelect = document.getElementById("sd-reports-filter-status");

  function apiUrl(baseUrl) {
    if (!statusFilterSelect || !statusFilterSelect.value) return baseUrl;
    const sep = baseUrl.indexOf("?") >= 0 ? "&" : "?";
    return (
      baseUrl + sep + "status=" + encodeURIComponent(statusFilterSelect.value)
    );
  }

  async function fetchJson(url) {
    const res = await fetch(url, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      const err = new Error("Request failed: " + res.status);
      err.status = res.status;
      return Promise.reject(err);
    }
    return res.json();
  }

  function escapeHtml(text) {
    const d = document.createElement("div");
    d.textContent = text == null ? "" : String(text);
    return d.innerHTML;
  }

  function renderSummary(data) {
    summaryOut.innerHTML = "";
    if (!Array.isArray(data) || data.length === 0) {
      summaryOut.innerHTML =
        '<p class="text-muted mb-0">No ticket data yet.</p>';
      return;
    }
    const row = document.createElement("div");
    row.className = "row g-3";
    data.forEach(function (item) {
      const col = document.createElement("div");
      col.className = "col-sm-6 col-md-4";
      col.innerHTML =
        '<div class="card border-0 shadow-sm h-100 sd-card">' +
        '<div class="card-body">' +
        '<p class="small text-muted text-uppercase mb-1">' +
        escapeHtml(item.status) +
        "</p>" +
        '<p class="h4 mb-0 fw-semibold">' +
        escapeHtml(String(item.count)) +
        "</p>" +
        "</div></div>";
      row.appendChild(col);
    });
    summaryOut.appendChild(row);
  }

  function formatWhen(iso) {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleString();
    } catch (_) {
      return String(iso);
    }
  }

  function renderTickets(data) {
    ticketsOut.innerHTML = "";
    if (!Array.isArray(data) || data.length === 0) {
      ticketsOut.innerHTML =
        '<p class="text-muted mb-0">No tickets in the system.</p>';
      return;
    }
    const table = document.createElement("table");
    table.className = "table table-hover mb-0 align-middle sd-table small";
    table.innerHTML =
      "<thead><tr>" +
      '<th scope="col" class="ps-4">ID</th>' +
      '<th scope="col">Title</th>' +
      '<th scope="col">Status</th>' +
      '<th scope="col">Priority</th>' +
      '<th scope="col">Submitted by</th>' +
      '<th scope="col">Assigned to</th>' +
      '<th scope="col">Created</th>' +
      '<th scope="col" class="pe-4">Description</th>' +
      "</tr></thead>";
    const tbody = document.createElement("tbody");
    data.forEach(function (t) {
      const tr = document.createElement("tr");
      const desc = t.description != null ? String(t.description) : "";
      const preview =
        desc.length > 100 ? escapeHtml(desc.slice(0, 100)) + "…" : escapeHtml(desc || "—");
      const who =
        escapeHtml(t.created_by_name || "—") +
        (t.created_by_email
          ? ' <span class="text-muted">(' +
            escapeHtml(t.created_by_email) +
            ")</span>"
          : "");
      const assign = t.assigned_to_name
        ? escapeHtml(t.assigned_to_name)
        : '<span class="text-muted">—</span>';
      const titleCell =
        '<a href="/tickets/' +
        escapeHtml(String(t.id)) +
        '" class="sd-link fw-medium">' +
        escapeHtml(t.title) +
        "</a>";
      tr.innerHTML =
        '<td class="ps-4 text-muted text-nowrap">#' +
        escapeHtml(String(t.id)) +
        "</td>" +
        "<td>" +
        titleCell +
        "</td>" +
        '<td><span class="text-nowrap">' +
        escapeHtml(t.status || "—") +
        "</span></td>" +
        '<td><span class="text-nowrap">' +
        escapeHtml(t.priority || "Medium") +
        "</span></td>" +
        "<td>" +
        who +
        "</td>" +
        "<td>" +
        assign +
        "</td>" +
        '<td class="text-muted text-nowrap">' +
        escapeHtml(formatWhen(t.created_at)) +
        "</td>" +
        '<td class="pe-4 text-muted">' +
        preview +
        "</td>";
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    ticketsOut.appendChild(table);
  }

  async function loadAll() {
    statusEl.textContent = "Loading…";
    statusEl.className = "small text-muted";
    summaryOut.innerHTML =
      '<p class="text-muted mb-0 placeholder-glow">Loading summary…</p>';
    ticketsOut.innerHTML =
      '<p class="text-muted mb-0 placeholder-glow">Loading tickets…</p>';

    try {
      /* Sequential requests: one shared DB connection server-side cannot safely run
         two cursors at the same time if the dev server handles requests in parallel. */
      const summary = await fetchJson(apiUrl(summaryUrl));
      renderSummary(summary);
      const tickets = await fetchJson(apiUrl(ticketsUrl));
      renderTickets(tickets);
      statusEl.textContent =
        "Last updated: " + new Date().toLocaleString();
      statusEl.className = "small text-success";
    } catch (e) {
      var msg;
      if (e.status === 401) {
        msg = "Not logged in. Sign in and open this page again.";
      } else if (e.status === 403) {
        msg =
          "Access denied. The statistics API is restricted to administrator accounts. Use “All tickets” for day-to-day queue work.";
      } else if (e.status >= 500) {
        msg =
          "Server error (" +
          e.status +
          "). Check the Flask terminal for the traceback; restart MySQL and Flask if needed.";
      } else if (e.status) {
        msg = "Request failed (HTTP " + e.status + "). Check the Flask terminal for a traceback.";
      } else {
        msg =
          (e.message ? e.message + " — " : "") +
          "Could not load statistics. Check that the app is running.";
      }
      statusEl.textContent = msg;
      statusEl.className = "small text-danger";
      summaryOut.innerHTML = "";
      ticketsOut.innerHTML = "";
    }
  }

  refreshBtn.addEventListener("click", function (e) {
    e.preventDefault();
    loadAll();
  });

  if (statusFilterSelect) {
    statusFilterSelect.addEventListener("change", function () {
      loadAll();
    });
  }

  loadAll();
})();

/** Registration form: client-side validation before POST (assignment: dynamic JS). */
(function initRegisterValidation() {
  const form = document.getElementById("sd-register-form");
  if (!form) return;
  const feedback = document.getElementById("sd-register-feedback");
  if (!feedback) return;

  form.addEventListener("submit", function (e) {
    const nameEl = form.querySelector('[name="name"]');
    const emailEl = form.querySelector('[name="email"]');
    const passwordEl = form.querySelector('[name="password"]');
    const name = nameEl ? nameEl.value.trim() : "";
    const email = emailEl ? emailEl.value.trim() : "";
    const password = passwordEl ? passwordEl.value : "";

    const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    let message = "";

    if (name.length < 2) {
      message = "Please enter your full name (at least 2 characters).";
    } else if (!emailOk) {
      message = "Please enter a valid email address.";
    } else if (password.length < 6) {
      message = "Password must be at least 6 characters.";
    }

    if (message) {
      e.preventDefault();
      feedback.textContent = message;
      feedback.classList.remove("d-none");
      feedback.classList.add("d-block");
    } else {
      feedback.classList.add("d-none");
      feedback.classList.remove("d-block");
    }
  });
})();
