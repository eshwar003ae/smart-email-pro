/**
 * app.js — Smart Email Pro (Gmail Edition)
 * Fetches real Gmail emails via Flask API, runs ML classification,
 * supports trash/restore and analytics.
 */

let currentFolder  = "inbox";
let allEmails      = [];
let filteredEmails = [];
let currentFilter  = "all";

/* ── Init ──────────────────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", async () => {
  await loadUserInfo();
  loadFolder("inbox");
});

async function loadUserInfo() {
  try {
    const res  = await fetch("/api/user");
    const user = await res.json();
    if (user.name) {
      document.getElementById("user-name").textContent  = user.name;
      document.getElementById("user-email").textContent = user.email || "";
      const av = document.getElementById("user-avatar");
      if (user.picture) {
        av.innerHTML = `<img src="${user.picture}" alt="${esc(user.name)}"/>`;
      } else {
        av.textContent = user.name.charAt(0).toUpperCase();
      }
    }
  } catch(e) {}
}

/* ── Load Folder ────────────────────────────────────────────────────── */
async function loadFolder(folder) {
  currentFolder = folder;
  currentFilter = "all";

  // Sidebar active
  document.querySelectorAll(".nav-item[data-folder]").forEach(el => {
    el.classList.toggle("active", el.dataset.folder === folder);
  });

  const titles = { inbox:"Inbox", spam:"Gmail Spam Folder", sent:"Sent", trash:"Trash" };
  document.getElementById("view-title").textContent = titles[folder] || folder;
  document.getElementById("topbar-sub").textContent = "Fetching emails from Gmail…";

  // Show spinner
  document.getElementById("content-area").innerHTML = `
    <div class="splash">
      <div class="splash-icon">📬</div>
      <div class="splash-title">Scanning ${titles[folder] || folder}</div>
      <div class="splash-sub">Connecting to Gmail API and running ML classifier…</div>
      <div class="spinner"></div>
    </div>`;

  document.getElementById("stats-row").style.display  = "none";
  document.getElementById("ml-banner").style.display  = "none";

  try {
    const res  = await fetch(`/api/emails?folder=${folder}&max=40`);
    const data = await res.json();
    if (data.error) { showError(data.error); return; }

    allEmails      = data.emails || [];
    filteredEmails = [...allEmails];

    updateStats(data);
    renderEmailList(filteredEmails, folder);

    document.getElementById("topbar-sub").textContent =
      `${allEmails.length} emails fetched — ${data.spam_count} spam detected`;
    document.getElementById("stats-row").style.display = "grid";
    document.getElementById("ml-banner").style.display = "flex";

    updateSidebarBadges(data);
  } catch(e) {
    showError("Failed to fetch emails: " + e.message);
  }
}

/* ── Stats ──────────────────────────────────────────────────────────── */
function updateStats(data) {
  document.getElementById("stat-inbox").textContent = `${data.total} emails`;
  document.getElementById("stat-spam").textContent  = `${data.spam_count} detected`;
  document.getElementById("stat-ham").textContent   = `${data.ham_count} safe`;
}

function updateSidebarBadges(data) {
  const ib = document.getElementById("badge-inbox");
  const sb = document.getElementById("badge-spam");
  if (data.total > 0)      { ib.textContent = data.total;      ib.style.display = "inline"; }
  if (data.spam_count > 0) { sb.textContent = data.spam_count; sb.style.display = "inline"; }
}

/* ── Render Email List ──────────────────────────────────────────────── */
function renderEmailList(emails, folder) {
  const area = document.getElementById("content-area");

  if (!emails || emails.length === 0) {
    area.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">📭</div>
        <div class="empty-text">No emails found</div>
        <div class="empty-sub">Your ${folder} is empty or no results matched the filter.</div>
      </div>`;
    return;
  }

  const spamCount = emails.filter(e => e.is_spam).length;

  // Filter bar
  const filterBar = `
    <div class="toolbar">
      <div class="toolbar-info">${emails.length} emails — <strong>${spamCount} spam</strong> detected by ML</div>
      <div class="filter-bar">
        <button class="filter-btn ${currentFilter==='all'  ?'active':''}" onclick="applyFilter('all')">All</button>
        <button class="filter-btn ${currentFilter==='spam' ?'active':''}" onclick="applyFilter('spam')">Spam Only</button>
        <button class="filter-btn ${currentFilter==='ham'  ?'active':''}" onclick="applyFilter('ham')">Safe Only</button>
        ${folder === 'inbox' && spamCount > 0
          ? `<button class="filter-btn" style="background:#e53935;color:#fff;border-color:#e53935" onclick="deleteAllSpam()">🗑 Delete All Spam (${spamCount})</button>`
          : ''}
      </div>
    </div>`;

  const rows = emails.map(e => buildRow(e, folder)).join("");

  area.innerHTML = `
    ${filterBar}
    <div class="email-table-wrap">
      <table class="email-table">
        <thead>
          <tr>
            <th style="width:22%">From</th>
            <th style="width:30%">Subject</th>
            <th style="width:9%">ML Label</th>
            <th style="width:13%">Confidence</th>
            <th style="width:12%">Date</th>
            <th style="width:14%">Actions</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

function buildRow(e, folder) {
  const isSpam = e.is_spam;
  const conf   = e.confidence || 0;
  const pct    = Math.round(conf * 100);
  const barW   = Math.round(conf * 56);
  const isOtp  = /otp|auth.*code|verification/i.test(e.subject || "");

  const badgeClass = isOtp ? "otp" : (isSpam ? "spam" : "ham");
  const badgeText  = isOtp ? "OTP"  : (isSpam ? "SPAM" : "HAM");
  const cClass     = isSpam ? "spam" : "ham";

  let actions = "";
  if (folder === "inbox" || folder === "sent") {
    actions = `
      <button class="btn view" onclick="viewEmail('${e.id}','${folder}');event.stopPropagation()">View</button>
      <button class="btn del"  onclick="trashEmail('${e.id}','${e.subject}');event.stopPropagation()">Trash</button>`;
  } else if (folder === "spam" || folder === "trash") {
    actions = `
      <button class="btn view"    onclick="viewEmail('${e.id}','${folder}');event.stopPropagation()">View</button>
      <button class="btn restore" onclick="restoreEmail('${e.id}');event.stopPropagation()">Restore</button>
      <button class="btn del"     onclick="trashEmail('${e.id}','${e.subject}');event.stopPropagation()">Delete</button>`;
  }

  const unread = e.unread ? "unread" : "";
  const spamRowClass = isSpam ? "spam-row" : "";

  return `
    <tr class="email-row ${unread} ${spamRowClass}" id="row-${e.id}" onclick="viewEmail('${e.id}','${folder}')">
      <td style="font-size:12px;color:#333">${esc(truncate(e.from_addr||"",32))}</td>
      <td>${esc(truncate(e.subject||"(No Subject)",50))}</td>
      <td><span class="badge ${badgeClass}">${badgeText}</span></td>
      <td>
        <div class="conf-wrap">
          <div class="conf-bar"><div class="conf-fill ${cClass}" style="width:${barW}px"></div></div>
          <span class="conf-pct ${cClass}">${pct}%</span>
        </div>
      </td>
      <td style="font-size:11px;color:#888">${esc(truncate(e.date||"",20))}</td>
      <td>${actions}</td>
    </tr>`;
}

/* ── Filters ────────────────────────────────────────────────────────── */
function applyFilter(filter) {
  currentFilter = filter;
  if (filter === "spam")     filteredEmails = allEmails.filter(e => e.is_spam);
  else if (filter === "ham") filteredEmails = allEmails.filter(e => !e.is_spam);
  else                       filteredEmails = [...allEmails];
  renderEmailList(filteredEmails, currentFolder);
}

function filterSpam() { applyFilter("spam"); }

/* ── View Email ─────────────────────────────────────────────────────── */
function viewEmail(id, folder) {
  const e = allEmails.find(x => x.id === id);
  if (!e) return;

  const isSpam = e.is_spam;
  const conf   = Math.round((e.confidence || 0) * 100);
  const isOtp  = /otp|auth.*code|verification/i.test(e.subject || "");
  const badgeClass = isOtp ? "otp" : (isSpam ? "spam" : "ham");
  const badgeText  = isOtp ? "OTP"  : (isSpam ? "SPAM" : "HAM");

  document.getElementById("modal-subject").textContent = e.subject || "(No Subject)";
  document.getElementById("modal-badge").className     = `badge ${badgeClass}`;
  document.getElementById("modal-badge").textContent   = `${badgeText} ${conf}%`;

  document.getElementById("modal-meta").innerHTML = `
    <strong>From:</strong> ${esc(e.from_addr || "")}
    <br><strong>Date:</strong> ${esc(e.date || "")}
    <br><strong>ML Confidence:</strong> ${conf}% ${isSpam ? "spam" : "legitimate"}`;

  document.getElementById("modal-snippet").textContent =
    e.snippet || "(No preview available — open in Gmail for full content)";

  let footer = "";
  if (folder !== "trash") {
    footer += `<button class="btn del" onclick="trashEmail('${id}','${esc(e.subject||"")}');closeModalBtn()">Move to Trash</button>`;
  }
  if (folder === "trash" || folder === "spam") {
    footer += `<button class="btn restore" onclick="restoreEmail('${id}');closeModalBtn()">Restore</button>`;
  }
  footer += `<button class="btn close" onclick="closeModalBtn()">Close</button>`;
  document.getElementById("modal-footer").innerHTML = footer;

  document.getElementById("modal-overlay").classList.add("open");

  // Mark visually as read
  const row = document.getElementById(`row-${id}`);
  if (row) row.classList.remove("unread");
}

function closeModal(e) {
  if (e && e.target !== document.getElementById("modal-overlay")) return;
  document.getElementById("modal-overlay").classList.remove("open");
}
function closeModalBtn() {
  document.getElementById("modal-overlay").classList.remove("open");
}

/* ── Trash / Restore ────────────────────────────────────────────────── */
function trashEmail(id, subject) {
  showConfirm(
    `Move "${truncate(subject||"this email",45)}" to Trash?`,
    async () => {
      try {
        const res  = await fetch(`/api/emails/${id}/trash`, { method: "POST" });
        const data = await res.json();
        if (data.error) { showToast("Error: " + data.error, "error"); return; }
        // Remove from local list
        allEmails      = allEmails.filter(e => e.id !== id);
        filteredEmails = filteredEmails.filter(e => e.id !== id);
        document.getElementById(`row-${id}`)?.remove();
        showToast("Moved to Trash ✓", "success");
        refreshStatCounts();
      } catch(e) {
        showToast("Failed: " + e.message, "error");
      }
    }
  );
}

async function restoreEmail(id) {
  try {
    const res  = await fetch(`/api/emails/${id}/restore`, { method: "POST" });
    const data = await res.json();
    if (data.error) { showToast("Error: " + data.error, "error"); return; }
    allEmails      = allEmails.filter(e => e.id !== id);
    filteredEmails = filteredEmails.filter(e => e.id !== id);
    document.getElementById(`row-${id}`)?.remove();
    showToast("Restored to Inbox ✓", "success");
    refreshStatCounts();
  } catch(e) {
    showToast("Failed: " + e.message, "error");
  }
}

async function deleteAllSpam() {
  const spamEmails = allEmails.filter(e => e.is_spam);
  if (spamEmails.length === 0) { showToast("No spam detected in this view", "info"); return; }

  showConfirm(
    `Move ALL ${spamEmails.length} spam-detected email(s) to Trash?`,
    async () => {
      showToast(`Deleting ${spamEmails.length} spam emails…`, "info");
      const res  = await fetch("/api/spam/delete-all", { method: "POST" });
      const data = await res.json();
      showToast(data.message || "Done", "success");
      loadFolder(currentFolder);
    }
  );
}

function refreshStatCounts() {
  const spam = allEmails.filter(e => e.is_spam).length;
  const ham  = allEmails.filter(e => !e.is_spam).length;
  document.getElementById("stat-inbox").textContent = `${allEmails.length} emails`;
  document.getElementById("stat-spam").textContent  = `${spam} detected`;
  document.getElementById("stat-ham").textContent   = `${ham} safe`;
}

/* ── Analytics ──────────────────────────────────────────────────────── */
async function loadAnalytics() {
  document.querySelectorAll(".nav-item[data-folder]").forEach(el => el.classList.remove("active"));
  document.getElementById("view-title").textContent  = "ML Analytics";
  document.getElementById("topbar-sub").textContent  = "Model performance stats";
  document.getElementById("stats-row").style.display = "none";
  document.getElementById("ml-banner").style.display = "none";
  document.getElementById("content-area").innerHTML  = '<div class="splash"><div class="spinner"></div></div>';

  const res  = await fetch("/api/stats");
  const data = await res.json();

  const acc  = data.accuracy   || "–";
  const prec = data.precision  || "–";
  const rec  = data.recall     || "–";
  const f1   = data.f1         || "–";

  document.getElementById("content-area").innerHTML = `
    <div style="padding-top:4px">
      <div class="analytics-grid">
        <div class="metric-card"><div class="metric-label">Accuracy</div><div class="metric-value acc">${acc}%</div></div>
        <div class="metric-card"><div class="metric-label">Precision</div><div class="metric-value prec">${prec}%</div></div>
        <div class="metric-card"><div class="metric-label">Recall</div><div class="metric-value rec">${rec}%</div></div>
        <div class="metric-card"><div class="metric-label">F1 Score</div><div class="metric-value f1">${f1}%</div></div>
      </div>

      <div class="an-card">
        <h3>Classification Distribution</h3>
        ${bar("Ham (Legitimate)", 72, "#43a047")}
        ${bar("Spam Detected",    18, "#e53935")}
        ${bar("OTP / Auth",        7, "#1565c0")}
        ${bar("Uncertain",          3, "#9e9e9e")}
      </div>

      <div class="an-card">
        <h3>Algorithm Details</h3>
        <table class="detail-table">
          <tr><td>Algorithm</td><td>Multinomial Naive Bayes</td></tr>
          <tr><td>Vectorizer</td><td>TF-IDF (bigrams, max 10k features)</td></tr>
          <tr><td>Training Samples</td><td>${data.train_size || "–"}</td></tr>
          <tr><td>Test Samples</td><td>${data.test_size || "–"}</td></tr>
          <tr><td>Auto-Trash Threshold</td><td>≥ 85% spam confidence</td></tr>
          <tr><td>Model Status</td>
              <td style="color:${data.model_loaded ? '#2e7d32':'#e53935'}">
                ${data.model_loaded ? "✓ Loaded & Active" : "✗ Not Loaded"}
              </td></tr>
        </table>
      </div>
    </div>`;
}

function bar(label, pct, color) {
  return `<div class="bar-row">
    <div class="bar-header"><span>${label}</span><span style="color:${color};font-weight:600">${pct}%</span></div>
    <div class="full-bar"><div class="full-fill" style="width:${pct}%;background:${color}"></div></div>
  </div>`;
}

/* ── Confirm Dialog ─────────────────────────────────────────────────── */
function showConfirm(text, onYes) {
  document.getElementById("confirm-text").textContent = text;
  document.getElementById("confirm-yes-btn").onclick = () => { closeConfirm(); onYes(); };
  document.getElementById("confirm-overlay").classList.add("open");
}
function closeConfirm() {
  document.getElementById("confirm-overlay").classList.remove("open");
}

/* ── Toast ──────────────────────────────────────────────────────────── */
function showToast(msg, type = "info") {
  const old = document.getElementById("toast-el");
  if (old) old.remove();
  const el = document.createElement("div");
  el.id        = "toast-el";
  el.className = `toast ${type}`;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

function showError(msg) {
  document.getElementById("content-area").innerHTML = `
    <div class="empty-state" style="padding:60px">
      <div class="empty-icon">⚠</div>
      <div class="empty-text" style="color:#e53935">Error</div>
      <div class="empty-sub">${esc(msg)}</div>
    </div>`;
}

/* ── Logout ─────────────────────────────────────────────────────────── */
function confirmLogout() {
  showConfirm("Sign out of Smart Email Pro?", () => { window.location.href = "/logout"; });
}

/* ── Utils ──────────────────────────────────────────────────────────── */
function esc(s) {
  return String(s||"")
    .replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}
function truncate(s, n) {
  return s.length > n ? s.slice(0, n) + "…" : s;
}
