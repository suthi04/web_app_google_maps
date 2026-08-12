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

/* ---------- Persistent background-analysis tracker ---------- */
const ACTIVE_ANALYSIS_JOB_KEY = "insightreview.activeAnalysisJob.v1";
const ANALYSIS_STAGE_LABELS = {
  queued: "รอคิว",
  fetching_reviews: "กำลังดึงรีวิว",
  preprocessing: "กำลังเตรียมข้อความ",
  sentiment: "กำลังวิเคราะห์อารมณ์",
  aspects: "กำลังจัดหมวดความคิดเห็น",
  phrases: "กำลังสกัดวลีสำคัญ",
  insights: "กำลังสร้างข้อเสนอแนะ",
  finalizing: "กำลังบันทึกผลลัพธ์",
  completed: "เสร็จสมบูรณ์",
  failed: "ไม่สำเร็จ",
};
let _activeAnalysisJob = null;
let _analysisTrackerTimer = null;
let _analysisTrackerErrors = 0;

function _readActiveAnalysisJob() {
  try {
    const parsed = JSON.parse(localStorage.getItem(ACTIVE_ANALYSIS_JOB_KEY) || "null");
    return parsed && parsed.jobId && parsed.apiUrl && parsed.jobUrl ? parsed : null;
  } catch (_) {
    return null;
  }
}

function _writeActiveAnalysisJob(job) {
  _activeAnalysisJob = job;
  try {
    if (job) localStorage.setItem(ACTIVE_ANALYSIS_JOB_KEY, JSON.stringify(job));
    else localStorage.removeItem(ACTIVE_ANALYSIS_JOB_KEY);
  } catch (_) {}
}

function _trackerElements() {
  return {
    root: document.getElementById("analysisTracker"),
    title: document.getElementById("analysisTrackerTitle"),
    stage: document.getElementById("analysisTrackerStage"),
    percent: document.getElementById("analysisTrackerPercent"),
    progress: document.getElementById("analysisTrackerProgress"),
    link: document.getElementById("analysisTrackerLink"),
    close: document.getElementById("analysisTrackerClose"),
  };
}

function _hideAnalysisTracker() {
  const { root } = _trackerElements();
  if (root) root.hidden = true;
  clearTimeout(_analysisTrackerTimer);
}

function _renderAnalysisTracker(job) {
  const ui = _trackerElements();
  if (!ui.root || !job) return;
  const status = job.status || "queued";
  const value = Math.max(0, Math.min(100, Number(job.progress) || 0));
  const done = status === "completed" && (job.dashboard_url || job.dashboardUrl);
  const failed = status === "failed";

  ui.root.hidden = false;
  ui.root.classList.toggle("completed", done);
  ui.root.classList.toggle("failed", failed);
  ui.title.textContent = done
    ? "วิเคราะห์เสร็จแล้ว"
    : failed ? "วิเคราะห์ไม่สำเร็จ" : "กำลังวิเคราะห์รีวิว";
  ui.stage.textContent = failed
    ? (job.error_message || "กรุณาเปิดดูรายละเอียด")
    : (ANALYSIS_STAGE_LABELS[job.stage || status] || "กำลังประมวลผล");
  ui.percent.textContent = done ? "100%" : `${value}%`;
  ui.progress.value = done ? 100 : value;
  ui.progress.textContent = `${done ? 100 : value}%`;
  ui.link.href = done
    ? (job.dashboard_url || job.dashboardUrl)
    : (_activeAnalysisJob?.jobUrl || "#");
  ui.link.textContent = done ? "เปิดผลลัพธ์" : failed ? "ดูรายละเอียด" : "ดูสถานะ";
  ui.close.hidden = !(done || failed);
}

function _scheduleAnalysisTracker(delay = 1800) {
  clearTimeout(_analysisTrackerTimer);
  if (!_activeAnalysisJob || document.getElementById("jobCard")) return;
  _analysisTrackerTimer = setTimeout(_pollAnalysisTracker, delay);
}

async function _pollAnalysisTracker() {
  if (!_activeAnalysisJob || document.getElementById("jobCard")) return;
  try {
    const response = await fetch(_activeAnalysisJob.apiUrl, {
      headers: { "Accept": "application/json" },
      cache: "no-store",
    });
    if (response.status === 404) {
      window.analysisTracker.clear();
      return;
    }
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const job = await response.json();
    _analysisTrackerErrors = 0;
    _renderAnalysisTracker(job);

    if (job.status === "completed" && (job.dashboard_url || job.analysis_id)) {
      const dashboardUrl = job.dashboard_url || `/dashboard/${job.analysis_id}`;
      const shouldNotify = !_activeAnalysisJob.notified;
      _writeActiveAnalysisJob({
        ..._activeAnalysisJob,
        status: "completed",
        dashboardUrl,
        notified: true,
      });
      if (shouldNotify) toast("วิเคราะห์เสร็จแล้ว เปิดดูผลลัพธ์ได้เลย", "ok", 5200);
      return;
    }
    if (job.status === "failed") {
      _writeActiveAnalysisJob({ ..._activeAnalysisJob, status: "failed" });
      return;
    }
    _scheduleAnalysisTracker(document.hidden ? 9000 : 1800);
  } catch (_) {
    _analysisTrackerErrors += 1;
    const ui = _trackerElements();
    if (ui.root) ui.root.hidden = false;
    if (ui.title) ui.title.textContent = "งานยังทำอยู่เบื้องหลัง";
    if (ui.stage) ui.stage.textContent = "กำลังเชื่อมต่อสถานะอีกครั้ง";
    _scheduleAnalysisTracker(Math.min(15000, 1800 * (2 ** Math.min(_analysisTrackerErrors, 3))));
  }
}

function _refreshAnalysisTracker() {
  _activeAnalysisJob = _readActiveAnalysisJob() || _activeAnalysisJob;
  if (!_activeAnalysisJob) {
    _hideAnalysisTracker();
    return;
  }
  const currentJobId = document.getElementById("jobCard")?.dataset.jobId;
  if (currentJobId === _activeAnalysisJob.jobId) {
    _hideAnalysisTracker();
    return;
  }
  _renderAnalysisTracker({
    status: _activeAnalysisJob.status || "queued",
    stage: _activeAnalysisJob.status || "queued",
    progress: _activeAnalysisJob.status === "completed" ? 100 : 0,
    dashboard_url: _activeAnalysisJob.dashboardUrl,
  });
  _scheduleAnalysisTracker(0);
}

window.analysisTracker = {
  track(job) {
    if (!job?.jobId || !job?.apiUrl || !job?.jobUrl) return;
    _writeActiveAnalysisJob({ ...job, status: "queued", startedAt: Date.now() });
    _refreshAnalysisTracker();
  },
  clear() {
    _writeActiveAnalysisJob(null);
    _hideAnalysisTracker();
  },
  refresh: _refreshAnalysisTracker,
};

document.getElementById("analysisTrackerClose")?.addEventListener("click", () => {
  window.analysisTracker.clear();
});
document.getElementById("analysisTrackerLink")?.addEventListener("click", () => {
  if (_activeAnalysisJob?.status === "completed") window.analysisTracker.clear();
});
window.addEventListener("storage", (event) => {
  if (event.key !== ACTIVE_ANALYSIS_JOB_KEY) return;
  _activeAnalysisJob = _readActiveAnalysisJob();
  if (_activeAnalysisJob) _refreshAnalysisTracker();
  else _hideAnalysisTracker();
});
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && _activeAnalysisJob && !document.getElementById("jobCard")) {
    _scheduleAnalysisTracker(0);
  }
});

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
        syncLandingPicker(field);
        syncModelMenuLabel(form);
      }));
      fields.forEach(syncLandingPicker);
    });
    // On a result page, the picker reflects the engine that actually produced
    // this analysis.  This also clears a stale saved fallback from an older run.
    if (form.dataset.syncResultEngine === "1") {
      const actualEngine = form.dataset.actualExtractEngine || "rule";
      const actualField = form.querySelector(
        `[name="extract_engine"][value="${actualEngine}"]`
      );
      if (actualField) actualField.checked = true;
      saved.extract_engine = actualEngine;
      try { localStorage.setItem(ANALYSIS_PREFS_KEY, JSON.stringify(saved)); } catch (_) {}
    }
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

  document.querySelectorAll(".landing-picker").forEach((picker) => {
    document.addEventListener("click", (event) => {
      if (!picker.contains(event.target)) picker.open = false;
    });
    picker.querySelectorAll("input").forEach((input) => input.addEventListener("change", () => {
      picker.open = false;
    }));
    picker.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        picker.open = false;
        picker.querySelector("summary")?.focus();
      }
    });
  });
}

function syncLandingPicker(field) {
  const picker = field?.closest(".landing-picker");
  if (!picker) return;
  const display = picker.querySelector("[data-select-display]");
  const selected = picker.querySelector(`input[name="${field.name}"]:checked`);
  const label = selected?.closest(".landing-picker-choice")?.querySelector("span");
  if (display && label) display.textContent = label.textContent;
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
  _refreshAnalysisTracker();

  // mobile nav toggle
  const toggle = document.getElementById("navToggle");
  const sidebar = document.getElementById("sidebar");
  const navClose = document.getElementById("navClose");
  const scrim = document.getElementById("scrim");
  const mobileNav = window.matchMedia("(max-width: 760px)");
  function setNavOpen(open, returnFocus = false) {
    open = Boolean(open && mobileNav.matches);
    document.body.classList.toggle("nav-open", open);
    toggle?.setAttribute("aria-expanded", open ? "true" : "false");
    toggle?.setAttribute("aria-label", open ? "ปิดเมนู" : "เปิดเมนู");
    if (sidebar && mobileNav.matches) {
      sidebar.inert = !open;
      sidebar.setAttribute("aria-hidden", open ? "false" : "true");
    }
    if (open) navClose?.focus();
    if (!open && returnFocus) toggle?.focus();
  }
  toggle?.addEventListener("click", () => {
    setNavOpen(!document.body.classList.contains("nav-open"));
  });
  navClose?.addEventListener("click", () => setNavOpen(false, true));
  scrim?.addEventListener("click", () => setNavOpen(false, true));
  sidebar?.querySelectorAll(".nav a").forEach((link) => {
    link.addEventListener("click", () => {
      if (mobileNav.matches) setNavOpen(false);
    });
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && document.body.classList.contains("nav-open")) {
      setNavOpen(false, true);
    }
  });
  function syncNavMode() {
    if (mobileNav.matches) {
      setNavOpen(false);
      return;
    }
    document.body.classList.remove("nav-open");
    toggle?.setAttribute("aria-expanded", "false");
    toggle?.setAttribute("aria-label", "เปิดเมนู");
    if (sidebar) {
      sidebar.inert = false;
      sidebar.removeAttribute("aria-hidden");
    }
  }
  mobileNav.addEventListener?.("change", syncNavMode);
  syncNavMode();
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
