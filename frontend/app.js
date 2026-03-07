/**
 * MailFlow – frontend application logic
 * Communicates with the Flask backend at /api/*
 */

const API = "";          // same origin
let allEmails = [];      // cached email list
let categories = [];     // cached categories
let templates = [];      // cached templates

// ============================================================
// Initialisation
// ============================================================

document.addEventListener("DOMContentLoaded", async () => {
  // Apply saved theme
  if (localStorage.getItem("dark") === "1") {
    document.documentElement.classList.add("dark");
  }

  await checkAuth();
  await loadStats();
  await loadEmails();
  await loadCategories();
  await loadTemplates();

  // Default page
  showPage("dashboard");
});

// ============================================================
// Authentication
// ============================================================

async function checkAuth() {
  try {
    const res = await fetch(`${API}/auth/status`);
    const data = await res.json();
    const statusEl = document.getElementById("connection-status");
    const authSection = document.getElementById("auth-section");
    const banner = document.getElementById("connect-banner");

    if (data.authenticated) {
      statusEl.textContent = "Gmail Connected ✓";
      statusEl.className =
        "text-xs font-medium px-3 py-1 rounded-full bg-green-100 dark:bg-green-900/20 text-green-700 dark:text-green-400";
      authSection.innerHTML = `
        <button onclick="gmailLogout()" class="nav-item w-full text-red-500 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
          </svg>
          Disconnect Gmail
        </button>`;
      if (banner) banner.classList.add("hidden");
    } else {
      statusEl.textContent = "Not connected";
      statusEl.className =
        "text-xs font-medium px-3 py-1 rounded-full bg-amber-100 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400";
      authSection.innerHTML = `
        <button onclick="gmailLogin()" class="nav-item w-full text-brand-600 dark:text-brand-400 hover:bg-brand-50 dark:hover:bg-brand-900/20">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1"/>
          </svg>
          Connect Gmail
        </button>`;
      if (banner) banner.classList.remove("hidden");
    }
  } catch (_) {
    // backend may be starting up
  }
}

async function gmailLogin() {
  try {
    const res = await fetch(`${API}/auth/login`);
    const data = await res.json();
    if (data.auth_url) {
      window.location.href = data.auth_url;
    } else {
      showToast(data.error || "Could not start login", "error");
    }
  } catch (err) {
    showToast("Backend unreachable: " + err.message, "error");
  }
}

async function gmailLogout() {
  await fetch(`${API}/auth/logout`, { method: "POST" });
  await checkAuth();
  showToast("Disconnected from Gmail");
}

// ============================================================
// Stats / Dashboard
// ============================================================

async function loadStats() {
  try {
    const res = await fetch(`${API}/api/stats`);
    if (!res.ok) return;
    const data = await res.json();
    document.getElementById("stat-total").textContent = data.total_emails ?? "–";
    document.getElementById("stat-unread").textContent = data.unread ?? "–";
    document.getElementById("stat-replied").textContent = data.replied ?? "–";
    document.getElementById("stat-categories").textContent = data.categories ?? "–";

    // Unread badge in sidebar
    const badge = document.getElementById("unread-badge");
    if (data.unread > 0) {
      badge.textContent = data.unread;
      badge.classList.remove("hidden");
    } else {
      badge.classList.add("hidden");
    }

    // Category breakdown bars
    const breakdown = document.getElementById("category-breakdown");
    if (data.by_category && data.by_category.length > 0) {
      const maxCount = Math.max(...data.by_category.map((c) => c.count), 1);
      breakdown.innerHTML = data.by_category
        .map(
          (c) => `
          <div class="flex items-center gap-3">
            <span class="w-3 h-3 rounded-full shrink-0" style="background:${c.color}"></span>
            <span class="text-sm w-32 truncate">${c.name}</span>
            <div class="flex-1 bg-gray-100 dark:bg-gray-800 rounded-full h-2 overflow-hidden">
              <div class="h-2 rounded-full" style="background:${c.color};width:${Math.round((c.count / maxCount) * 100)}%"></div>
            </div>
            <span class="text-sm text-gray-500 w-8 text-right">${c.count}</span>
          </div>`
        )
        .join("");
    } else {
      breakdown.innerHTML = `<p class="text-sm text-gray-400">No data yet – sync your inbox first.</p>`;
    }
  } catch (_) {}
}

// ============================================================
// Emails
// ============================================================

async function loadEmails() {
  try {
    const res = await fetch(`${API}/api/emails`);
    if (!res.ok) return;
    allEmails = await res.json();
    renderEmailList(allEmails);
    populateCategoryFilter();
  } catch (_) {}
}

async function syncEmails() {
  const btn = document.getElementById("sync-btn");
  btn.disabled = true;
  btn.querySelector("svg").classList.add("animate-spin");
  showToast("Syncing emails…", "info");
  try {
    const res = await fetch(`${API}/api/emails/sync`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.error || "Sync failed", "error");
    } else {
      showToast(data.message || "Sync complete");
      await loadEmails();
      await loadStats();
    }
  } catch (err) {
    showToast("Error: " + err.message, "error");
  } finally {
    btn.disabled = false;
    btn.querySelector("svg").classList.remove("animate-spin");
  }
}

function renderEmailList(emails) {
  const container = document.getElementById("email-list");
  if (!emails || emails.length === 0) {
    container.innerHTML = `<p class="text-sm text-gray-400 py-6 text-center">
      No emails found. Click <strong>Sync Inbox</strong> to load your emails.
    </p>`;
    return;
  }
  container.innerHTML = emails
    .map(
      (e) => `
    <div class="email-item ${!e.is_read ? "unread" : ""}" onclick="openEmail('${e.gmail_id}')">
      <div class="flex-1 min-w-0">
        <div class="flex items-center justify-between gap-2">
          <span class="text-sm font-semibold truncate max-w-xs">${escHtml(e.sender || "(unknown)")}</span>
          <span class="text-xs text-gray-400 shrink-0">${formatDate(e.date)}</span>
        </div>
        <p class="text-sm truncate mt-0.5 ${!e.is_read ? "font-medium" : "text-gray-600 dark:text-gray-400"}">${escHtml(e.subject || "(no subject)")}</p>
        <p class="text-xs text-gray-400 truncate mt-0.5">${escHtml(e.snippet || "")}</p>
      </div>
      <div class="shrink-0 flex flex-col items-end gap-1.5 ml-2">
        ${e.category_name ? `<span class="text-xs px-2 py-0.5 rounded-full font-medium text-white" style="background:${e.category_color || "#6366f1"}">${escHtml(e.category_name)}</span>` : ""}
        ${e.is_replied ? `<span class="text-xs text-green-500">↩ replied</span>` : ""}
      </div>
    </div>`
    )
    .join("");
}

function filterEmails() {
  const query = document.getElementById("search-input").value.toLowerCase();
  const catFilter = document.getElementById("filter-category").value;
  const filtered = allEmails.filter((e) => {
    const matchQuery =
      !query ||
      (e.subject || "").toLowerCase().includes(query) ||
      (e.sender || "").toLowerCase().includes(query) ||
      (e.snippet || "").toLowerCase().includes(query);
    const matchCat =
      !catFilter || String(e.category_id) === catFilter;
    return matchQuery && matchCat;
  });
  renderEmailList(filtered);
}

function populateCategoryFilter() {
  const sel = document.getElementById("filter-category");
  const current = sel.value;
  sel.innerHTML = `<option value="">All Categories</option>`;
  categories.forEach((c) => {
    sel.innerHTML += `<option value="${c.id}">${escHtml(c.name)}</option>`;
  });
  sel.value = current;
}

async function openEmail(gmailId) {
  showPage("email-detail");
  const container = document.getElementById("email-detail-content");
  container.innerHTML = `<p class="text-sm text-gray-400">Loading…</p>`;

  try {
    const res = await fetch(`${API}/api/emails/${gmailId}`);
    const email = await res.json();

    // Get templates for this category
    const catTemplates = email.category_id
      ? templates.filter((t) => t.category_id === email.category_id)
      : templates;

    const templateOptions = catTemplates
      .map((t) => `<option value="${t.id}">${escHtml(t.name)}</option>`)
      .join("");

    container.innerHTML = `
      <div class="flex items-start justify-between gap-4 mb-4">
        <div>
          <h2 class="text-xl font-bold">${escHtml(email.subject || "(no subject)")}</h2>
          <p class="text-sm text-gray-500 mt-1">From: ${escHtml(email.sender || "")}</p>
          <p class="text-sm text-gray-500">Date: ${formatDate(email.date)}</p>
          ${email.category_name ? `<span class="inline-block mt-2 text-xs px-2 py-0.5 rounded-full font-medium text-white" style="background:${email.category_color}">${escHtml(email.category_name)}</span>` : ""}
        </div>
        <button id="reply-btn-detail" class="btn-primary shrink-0">↩ Reply</button>
      </div>
      <hr class="border-gray-200 dark:border-gray-700 mb-4" />
      <div class="text-sm leading-relaxed whitespace-pre-wrap max-h-96 overflow-y-auto font-mono bg-gray-50 dark:bg-gray-800 rounded-lg p-4">${escHtml(email.body || email.snippet || "(empty)")}</div>
    `;
    // Attach reply handler via DOM API to avoid inline JS string injection
    document.getElementById("reply-btn-detail").addEventListener("click", () => {
      openReplyModal(email.gmail_id, email.subject || "", email.sender || "");
    });
  } catch (err) {
    container.innerHTML = `<p class="text-red-500 text-sm">Error: ${err.message}</p>`;
  }
}

// ============================================================
// Categories
// ============================================================

async function loadCategories() {
  try {
    const res = await fetch(`${API}/api/categories`);
    if (!res.ok) return;
    categories = await res.json();
    renderCategories();
    populateCategoryFilter();
    populateCategorySelects();
  } catch (_) {}
}

function renderCategories() {
  const container = document.getElementById("categories-list");
  if (!categories || categories.length === 0) {
    container.innerHTML = `<p class="text-sm text-gray-400 py-6 text-center">No categories yet. Create one to start organising your inbox.</p>`;
    return;
  }
  container.innerHTML = categories
    .map(
      (c) => `
    <div class="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 flex items-start gap-4">
      <span class="w-4 h-4 rounded-full mt-0.5 shrink-0" style="background:${c.color}"></span>
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2">
          <span class="font-semibold">${escHtml(c.name)}</span>
          <span class="text-xs text-gray-400">priority ${c.priority}</span>
        </div>
        ${c.description ? `<p class="text-sm text-gray-500 mt-0.5">${escHtml(c.description)}</p>` : ""}
        <div class="flex flex-wrap gap-3 mt-2 text-xs text-gray-500">
          ${c.sender_keywords ? `<span>📧 From: ${escHtml(c.sender_keywords)}</span>` : ""}
          ${c.subject_keywords ? `<span>📝 Subject: ${escHtml(c.subject_keywords)}</span>` : ""}
          ${c.body_keywords ? `<span>📄 Body: ${escHtml(c.body_keywords)}</span>` : ""}
        </div>
      </div>
      <div class="flex gap-2 shrink-0">
        <button onclick="editCategory(${c.id})" class="btn-ghost text-xs">Edit</button>
        <button onclick="deleteCategory(${c.id})" class="btn-danger">Delete</button>
      </div>
    </div>`
    )
    .join("");
}

function openCategoryModal(cat = null) {
  document.getElementById("cat-id").value = cat ? cat.id : "";
  document.getElementById("cat-name").value = cat ? cat.name : "";
  document.getElementById("cat-description").value = cat ? cat.description : "";
  document.getElementById("cat-color").value = cat ? cat.color : "#6366f1";
  document.getElementById("cat-priority").value = cat ? cat.priority : 0;
  document.getElementById("cat-sender").value = cat ? cat.sender_keywords : "";
  document.getElementById("cat-subject").value = cat ? cat.subject_keywords : "";
  document.getElementById("cat-body").value = cat ? cat.body_keywords : "";
  document.getElementById("category-modal-title").textContent = cat
    ? "Edit Category"
    : "New Category";
  document.getElementById("category-modal").classList.remove("hidden");
}

function closeCategoryModal() {
  document.getElementById("category-modal").classList.add("hidden");
}

function editCategory(id) {
  const cat = categories.find((c) => c.id === id);
  if (cat) openCategoryModal(cat);
}

async function deleteCategory(id) {
  if (!confirm("Delete this category? Emails will become uncategorised.")) return;
  const res = await fetch(`${API}/api/categories/${id}`, { method: "DELETE" });
  if (res.ok) {
    showToast("Category deleted.");
    await loadCategories();
    await loadStats();
  } else {
    const d = await res.json();
    showToast(d.error || "Delete failed", "error");
  }
}

async function saveCategory(event) {
  event.preventDefault();
  const id = document.getElementById("cat-id").value;
  const payload = {
    name: document.getElementById("cat-name").value,
    description: document.getElementById("cat-description").value,
    color: document.getElementById("cat-color").value,
    priority: document.getElementById("cat-priority").value,
    sender_keywords: document.getElementById("cat-sender").value,
    subject_keywords: document.getElementById("cat-subject").value,
    body_keywords: document.getElementById("cat-body").value,
  };
  const url = id ? `${API}/api/categories/${id}` : `${API}/api/categories`;
  const method = id ? "PUT" : "POST";
  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (res.ok) {
    showToast(id ? "Category updated." : "Category created.");
    closeCategoryModal();
    await loadCategories();
    await loadStats();
  } else {
    const d = await res.json();
    showToast(d.error || "Save failed", "error");
  }
}

// ============================================================
// Templates
// ============================================================

async function loadTemplates() {
  try {
    const res = await fetch(`${API}/api/templates`);
    if (!res.ok) return;
    templates = await res.json();
    renderTemplates();
    populateCategorySelects();
  } catch (_) {}
}

function renderTemplates() {
  const container = document.getElementById("templates-list");
  if (!templates || templates.length === 0) {
    container.innerHTML = `<p class="text-sm text-gray-400 py-6 text-center">No templates yet. Create one to enable auto-replies.</p>`;
    return;
  }
  container.innerHTML = templates
    .map((t) => {
      const cat = categories.find((c) => c.id === t.category_id);
      return `
    <div class="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4">
      <div class="flex items-start justify-between gap-4">
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="font-semibold">${escHtml(t.name)}</span>
            ${cat ? `<span class="text-xs px-2 py-0.5 rounded-full text-white font-medium" style="background:${cat.color}">${escHtml(cat.name)}</span>` : ""}
            ${t.auto_reply ? `<span class="text-xs px-2 py-0.5 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 font-medium">🤖 Auto-reply ON</span>` : ""}
          </div>
          <p class="text-xs text-gray-400 mt-1">Subject prefix: ${escHtml(t.subject_prefix)}</p>
          <p class="text-sm text-gray-600 dark:text-gray-300 mt-2 whitespace-pre-wrap max-h-20 overflow-hidden">${escHtml(t.body)}</p>
        </div>
        <div class="flex gap-2 shrink-0">
          <button onclick="editTemplate(${t.id})" class="btn-ghost text-xs">Edit</button>
          <button onclick="deleteTemplate(${t.id})" class="btn-danger">Delete</button>
        </div>
      </div>
    </div>`;
    })
    .join("");
}

function populateCategorySelects() {
  // Template modal category select
  const sel = document.getElementById("tmpl-category");
  if (!sel) return;
  const current = sel.value;
  sel.innerHTML = `<option value="">Select a category…</option>`;
  categories.forEach((c) => {
    sel.innerHTML += `<option value="${c.id}">${escHtml(c.name)}</option>`;
  });
  if (current) sel.value = current;
}

function openTemplateModal(tmpl = null) {
  document.getElementById("tmpl-id").value = tmpl ? tmpl.id : "";
  document.getElementById("tmpl-name").value = tmpl ? tmpl.name : "";
  document.getElementById("tmpl-subject-prefix").value = tmpl
    ? tmpl.subject_prefix
    : "Re: ";
  document.getElementById("tmpl-body").value = tmpl ? tmpl.body : "";
  document.getElementById("tmpl-auto").checked = tmpl ? tmpl.auto_reply : false;
  document.getElementById("template-modal-title").textContent = tmpl
    ? "Edit Template"
    : "New Reply Template";
  populateCategorySelects();
  document.getElementById("tmpl-category").value = tmpl ? tmpl.category_id : "";
  document.getElementById("template-modal").classList.remove("hidden");
}

function closeTemplateModal() {
  document.getElementById("template-modal").classList.add("hidden");
}

function editTemplate(id) {
  const tmpl = templates.find((t) => t.id === id);
  if (tmpl) openTemplateModal(tmpl);
}

async function deleteTemplate(id) {
  if (!confirm("Delete this template?")) return;
  const res = await fetch(`${API}/api/templates/${id}`, { method: "DELETE" });
  if (res.ok) {
    showToast("Template deleted.");
    await loadTemplates();
  } else {
    const d = await res.json();
    showToast(d.error || "Delete failed", "error");
  }
}

async function saveTemplate(event) {
  event.preventDefault();
  const id = document.getElementById("tmpl-id").value;
  const payload = {
    name: document.getElementById("tmpl-name").value,
    category_id: document.getElementById("tmpl-category").value,
    subject_prefix: document.getElementById("tmpl-subject-prefix").value,
    body: document.getElementById("tmpl-body").value,
    auto_reply: document.getElementById("tmpl-auto").checked,
  };
  const url = id ? `${API}/api/templates/${id}` : `${API}/api/templates`;
  const method = id ? "PUT" : "POST";
  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (res.ok) {
    showToast(id ? "Template updated." : "Template created.");
    closeTemplateModal();
    await loadTemplates();
  } else {
    const d = await res.json();
    showToast(d.error || "Save failed", "error");
  }
}

// ============================================================
// Reply modal
// ============================================================

let _replyEmailData = null;

function openReplyModal(gmailId, subject, sender) {
  _replyEmailData = { gmail_id: gmailId, subject, sender };
  document.getElementById("reply-gmail-id").value = gmailId;
  document.getElementById("reply-modal-subject").textContent = "Reply: " + subject;
  document.getElementById("reply-modal-to").textContent = "To: " + sender;
  document.getElementById("reply-subject").value = "Re: " + subject;
  document.getElementById("reply-body").value = "";

  // Populate template selector
  const sel = document.getElementById("reply-template-select");
  sel.innerHTML = `<option value="">Write manually…</option>`;
  templates.forEach((t) => {
    sel.innerHTML += `<option value="${t.id}">${escHtml(t.name)}</option>`;
  });
  sel.value = "";

  document.getElementById("reply-modal").classList.remove("hidden");
}

function closeReplyModal() {
  document.getElementById("reply-modal").classList.add("hidden");
}

function onReplyTemplateChange() {
  const id = parseInt(document.getElementById("reply-template-select").value);
  if (!id) return;
  const tmpl = templates.find((t) => t.id === id);
  if (tmpl && _replyEmailData) {
    const subject =
      (tmpl.subject_prefix || "Re: ") + (_replyEmailData.subject || "");
    let body = tmpl.body;
    body = body.replace("{sender}", _replyEmailData.sender || "");
    body = body.replace("{subject}", _replyEmailData.subject || "");
    document.getElementById("reply-subject").value = subject;
    document.getElementById("reply-body").value = body;
  }
}

async function sendReply() {
  const gmailId = document.getElementById("reply-gmail-id").value;
  const templateId = document.getElementById("reply-template-select").value;
  const subject = document.getElementById("reply-subject").value;
  const body = document.getElementById("reply-body").value;

  const payload = templateId
    ? { template_id: parseInt(templateId) }
    : { subject, body };

  try {
    const res = await fetch(`${API}/api/emails/${gmailId}/reply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.sent) {
      showToast("Reply sent! ✓");
      closeReplyModal();
      await loadEmails();
    } else {
      showToast(data.message || data.error || "Reply failed", "error");
    }
  } catch (err) {
    showToast("Error: " + err.message, "error");
  }
}

// ============================================================
// Navigation
// ============================================================

const PAGES = ["dashboard", "inbox", "email-detail", "categories", "templates"];

function showPage(page) {
  PAGES.forEach((p) => {
    const el = document.getElementById(`page-${p}`);
    if (el) el.classList.toggle("hidden", p !== page);
    const nav = document.getElementById(`nav-${p}`);
    if (nav) nav.classList.toggle("active", p === page);
  });
  const titles = {
    dashboard: "Dashboard",
    inbox: "Inbox",
    "email-detail": "Email",
    categories: "Categories",
    templates: "Reply Templates",
  };
  document.getElementById("page-title").textContent = titles[page] || "";
}

// ============================================================
// Dark mode
// ============================================================

function toggleDark() {
  const html = document.documentElement;
  html.classList.toggle("dark");
  localStorage.setItem("dark", html.classList.contains("dark") ? "1" : "0");
}

// ============================================================
// Toast notifications
// ============================================================

let _toastTimer = null;

function showToast(msg, type = "success") {
  const toast = document.getElementById("toast");
  const inner = document.getElementById("toast-inner");
  const icon = document.getElementById("toast-icon");
  const msgEl = document.getElementById("toast-msg");

  msgEl.textContent = msg;
  if (type === "error") {
    inner.className =
      "bg-red-600 text-white px-4 py-3 rounded-xl shadow-lg text-sm font-medium flex items-center gap-2 min-w-[200px]";
    icon.textContent = "✕";
  } else if (type === "info") {
    inner.className =
      "bg-blue-600 text-white px-4 py-3 rounded-xl shadow-lg text-sm font-medium flex items-center gap-2 min-w-[200px]";
    icon.textContent = "ℹ";
  } else {
    inner.className =
      "bg-gray-900 dark:bg-white text-white dark:text-gray-900 px-4 py-3 rounded-xl shadow-lg text-sm font-medium flex items-center gap-2 min-w-[200px]";
    icon.textContent = "✓";
  }

  toast.classList.remove("hidden");
  if (_toastTimer) clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => toast.classList.add("hidden"), 3500);
}

// ============================================================
// Utilities
// ============================================================

function escHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function escAttr(str) {
  if (!str) return "";
  // Escape for safe insertion into HTML attribute values
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function formatDate(dateStr) {
  if (!dateStr) return "";
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const diffDays = Math.floor((now - d) / 86400000);
    if (diffDays === 0)
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    if (diffDays < 7)
      return d.toLocaleDateString([], { weekday: "short" });
    return d.toLocaleDateString([], { month: "short", day: "numeric" });
  } catch (_) {
    return dateStr;
  }
}
