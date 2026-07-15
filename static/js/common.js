// common.js — UI utilities ใช้ร่วมทุกหน้า: toast / confirm modal / loading / mobile nav

/* ---------- Toast ---------- */
const ICONS = {
  ok:  '<path d="M5 12l5 5L20 7" stroke-linecap="round" stroke-linejoin="round"/>',
  err: '<path d="M6 6l12 12M18 6L6 18" stroke-linecap="round"/>',
  info:'<path d="M12 8h.01M11 12h1v4h1" stroke-linecap="round" stroke-linejoin="round"/>',
};
function toast(message, type = "ok", ms = 2800) {
  const wrap = document.getElementById("toastWrap");
  if (!wrap) return;
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  const icon = document.createElement("span");
  icon.className = "ti";
  icon.setAttribute("aria-hidden", "true");
  icon.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor">${ICONS[type] || ICONS.ok}</svg>`;
  const label = document.createElement("span");
  label.textContent = String(message);
  el.append(icon, label);
  wrap.appendChild(el);
  requestAnimationFrame(() => el.classList.add("show"));
  setTimeout(() => {
    el.classList.remove("show");
    setTimeout(() => el.remove(), 300);
  }, ms);
}
window.toast = toast;

/* ---------- CSRF ---------- */
function csrfHeaders() {
  const token = document.querySelector('meta[name="csrf-token"]')?.content;
  return token ? { "X-CSRF-Token": token } : {};
}
window.csrfHeaders = csrfHeaders;

/* ---------- Confirm modal ---------- */
let _confirmCb = null;
let _confirmReturnFocus = null;
function confirmDialog({ title, body, okText = "ลบ", onOk }) {
  const m = document.getElementById("confirmModal");
  if (!m) return;
  document.getElementById("confirmTitle").textContent = title || "ยืนยัน";
  document.getElementById("confirmBody").textContent = body || "";
  document.getElementById("confirmOk").textContent = okText;
  _confirmCb = onOk;
  _confirmReturnFocus = document.activeElement;
  m.inert = false;
  m.classList.add("open");
  m.setAttribute("aria-hidden", "false");
  document.getElementById("confirmCancel")?.focus();
}
window.confirmDialog = confirmDialog;

function _closeConfirm() {
  const modal = document.getElementById("confirmModal");
  if (!modal?.classList.contains("open")) return;
  modal.classList.remove("open");
  modal.setAttribute("aria-hidden", "true");
  modal.inert = true;
  _confirmCb = null;
  if (_confirmReturnFocus instanceof HTMLElement) _confirmReturnFocus.focus();
  _confirmReturnFocus = null;
}

/* ---------- Loading overlay ---------- */
function showLoading(on = true) {
  const overlay = document.getElementById("loadingOverlay");
  overlay?.classList.toggle("open", on);
  overlay?.setAttribute("aria-hidden", on ? "false" : "true");
}
window.showLoading = showLoading;

/* ---------- Prevent accidental duplicate analysis submissions ---------- */
function guardAnalysisForm(form) {
  if (!form || form.dataset.guardReady === "1") return;
  form.dataset.guardReady = "1";
  form.addEventListener("submit", (event) => {
    if (form.dataset.submitting === "1") {
      event.preventDefault();
      return;
    }
    form.dataset.submitting = "1";
    form.setAttribute("aria-busy", "true");
    form.querySelectorAll('button[type="submit"]').forEach((button) => {
      button.disabled = true;
    });
    showLoading(true);
  });
}

/* ---------- Remember per-analysis choices + ChatGPT-like model label ---------- */
const ANALYSIS_PREFS_KEY = "insightreview.analysisPreferences.v1";
function wireAnalysisPreferences() {
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(ANALYSIS_PREFS_KEY) || "{}"); } catch (_) {}

  document.querySelectorAll("form[data-guard-submit]").forEach((form) => {
    ["engine", "extract_engine", "max_reviews"].forEach((name) => {
      const fields = [...form.querySelectorAll(`[name="${name}"]`)];
      if (!fields.length) return;
      const wanted = String(saved[name] ?? "");
      if (wanted) {
        if (fields[0].type === "radio") {
          const match = fields.find((field) => field.value === wanted);
          if (match) match.checked = true;
        } else if ([...fields[0].options].some((option) => option.value === wanted)) {
          fields[0].value = wanted;
        }
      }
      fields.forEach((field) => field.addEventListener("change", () => {
        const current = field.type === "radio"
          ? form.querySelector(`[name="${name}"]:checked`)?.value
          : field.value;
        if (current) saved[name] = current;
        try { localStorage.setItem(ANALYSIS_PREFS_KEY, JSON.stringify(saved)); } catch (_) {}
        syncModelMenuLabel(form);
      }));
    });
    syncModelMenuLabel(form);
  });

  document.querySelectorAll(".model-menu").forEach((menu) => {
    document.addEventListener("click", (event) => {
      if (!menu.contains(event.target)) menu.open = false;
    });
    menu.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        menu.open = false;
        menu.querySelector("summary")?.focus();
      }
    });
  });
}

function syncModelMenuLabel(form) {
  const label = form.querySelector(".model-menu-label");
  if (!label) return;
  const engine = form.querySelector('[name="engine"]:checked')?.value || form.querySelector('[name="engine"]')?.value;
  const extract = form.querySelector('[name="extract_engine"]:checked')?.value || form.querySelector('[name="extract_engine"]')?.value;
  label.textContent = `${engine === "model" ? "WangchanBERTa" : "Lexicon"} + ${extract === "llm" ? "Gemini" : "Rule-based"}`;
}

/* ---------- Wire up ---------- */
document.addEventListener("DOMContentLoaded", () => {
  // confirm modal buttons
  document.getElementById("confirmCancel")?.addEventListener("click", _closeConfirm);
  document.getElementById("confirmOk")?.addEventListener("click", () => {
    const cb = _confirmCb;
    _closeConfirm();
    if (cb) cb();
  });
  document.getElementById("confirmModal")?.addEventListener("click", (e) => {
    if (e.target.id === "confirmModal") _closeConfirm();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") _closeConfirm();
    if (e.key !== "Tab") return;
    const modal = document.getElementById("confirmModal");
    if (!modal?.classList.contains("open")) return;
    const focusable = [...modal.querySelectorAll("button:not([disabled])")];
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  });

  document.querySelectorAll("form[data-guard-submit]").forEach(guardAnalysisForm);
  wireAnalysisPreferences();

  // mobile nav toggle
  const toggle = document.getElementById("navToggle");
  const scrim = document.getElementById("scrim");
  function setNavOpen(open) {
    document.body.classList.toggle("nav-open", open);
    toggle?.setAttribute("aria-expanded", open ? "true" : "false");
    toggle?.setAttribute("aria-label", open ? "ปิดเมนู" : "เปิดเมนู");
  }
  toggle?.addEventListener("click", () => {
    setNavOpen(!document.body.classList.contains("nav-open"));
  });
  scrim?.addEventListener("click", () => setNavOpen(false));
});

// Browsers may restore a page from the back/forward cache with old DOM state.
window.addEventListener("pageshow", () => {
  document.querySelectorAll("form[data-guard-submit]").forEach((form) => {
    delete form.dataset.submitting;
    form.removeAttribute("aria-busy");
    form.querySelectorAll('button[type="submit"]').forEach((button) => {
      button.disabled = false;
    });
  });
  showLoading(false);
});
