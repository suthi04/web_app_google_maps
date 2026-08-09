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
  label.textContent = `${engine === "model" ? "WangchanBERTa" : "Lexicon"} · ${extract === "llm" ? "Gemini" : "Rule-based"}`;
}

/* ---------- Persistent analysis job status across every page ---------- */
const ACTIVE_ANALYSIS_JOB_KEY = "insightreview.activeAnalysisJob.v1";
const ANALYSIS_JOB_STAGE_LABELS = {
  queued: "กำลังรอคิว",
  fetching_reviews: "กำลังดึงรีวิว",
  preprocessing: "กำลังเตรียมข้อความ",
  sentiment: "กำลังวิเคราะห์อารมณ์",
  aspects: "กำลังจัดหมวดความคิดเห็น",
  phrases: "กำลังสกัดประเด็นสำคัญ",
  insights: "กำลังสร้างข้อเสนอแนะ",
  finalizing: "กำลังบันทึกผลลัพธ์",
  completed: "ผลวิเคราะห์พร้อมแล้ว",
  failed: "งานวิเคราะห์ไม่สำเร็จ",
};
let trackedAnalysisJob = null;
let trackedAnalysisTimer = null;
let trackedAnalysisErrors = 0;

function readTrackedAnalysisJob() {
  try {
    const value = JSON.parse(localStorage.getItem(ACTIVE_ANALYSIS_JOB_KEY) || "null");
    return value && typeof value.id === "string" ? value : null;
  } catch (_) {
    return null;
  }
}

function writeTrackedAnalysisJob(job) {
  trackedAnalysisJob = job;
  try { localStorage.setItem(ACTIVE_ANALYSIS_JOB_KEY, JSON.stringify(job)); } catch (_) {}
}

function progressValue(job) {
  return Math.max(0, Math.min(100, Number(job?.progress) || 0));
}

function isTerminalJob(job) {
  return job?.status === "completed" || job?.status === "failed";
}

function trackedJobUrl(job) {
  if (job?.status === "completed" && job.dashboard_url) return job.dashboard_url;
  return job?.statusUrl || `/jobs/${encodeURIComponent(job?.id || "")}`;
}

function renderTrackedAnalysisJob(job) {
  const tracker = document.getElementById("analysisTracker");
  const historyCard = document.getElementById("historyActiveJob");
  if (!job) {
    if (tracker) tracker.hidden = true;
    if (historyCard) historyCard.hidden = true;
    const empty = document.getElementById("historyEmptyState");
    if (empty) empty.hidden = false;
    return;
  }

  const completed = job.status === "completed" && job.analysis_id;
  const failed = job.status === "failed";
  const pct = progressValue(job);
  const stageLabel = failed
    ? (job.error_message || ANALYSIS_JOB_STAGE_LABELS.failed)
    : (ANALYSIS_JOB_STAGE_LABELS[job.stage] || "กำลังประมวลผล");
  const title = completed
    ? "วิเคราะห์เสร็จแล้ว"
    : failed ? "วิเคราะห์ไม่สำเร็จ" : "กำลังวิเคราะห์รีวิว";
  const url = trackedJobUrl(job);

  if (tracker) {
    tracker.classList.toggle("completed", Boolean(completed));
    tracker.classList.toggle("failed", failed);
    tracker.hidden = Boolean(document.getElementById("jobCard"));
    document.getElementById("analysisTrackerTitle").textContent = title;
    document.getElementById("analysisTrackerStage").textContent = stageLabel;
    document.getElementById("analysisTrackerPercent").textContent = `${pct}%`;
    const trackerProgress = document.getElementById("analysisTrackerProgress");
    trackerProgress.value = pct;
    trackerProgress.textContent = `${pct}%`;
    document.getElementById("analysisTrackerLink").href = url;
    document.getElementById("analysisTrackerDismiss").hidden = !isTerminalJob(job);
  }

  if (historyCard) {
    const existingResult = completed
      ? document.querySelector(`.hist-card[data-id="${Number(job.analysis_id)}"]`)
      : null;
    historyCard.hidden = Boolean(existingResult);
    historyCard.classList.toggle("completed", Boolean(completed));
    historyCard.classList.toggle("failed", failed);
    document.getElementById("historyJobEyebrow").textContent = completed
      ? "ประมวลผลเสร็จแล้ว" : failed ? "งานมีปัญหา" : "กำลังประมวลผล";
    document.getElementById("historyJobTitle").textContent = completed
      ? "ผลวิเคราะห์ใหม่พร้อมดูแล้ว" : failed ? "งานวิเคราะห์ล่าสุดไม่สำเร็จ" : "งานวิเคราะห์ล่าสุด";
    document.getElementById("historyJobStage").textContent = stageLabel;
    document.getElementById("historyJobPercent").textContent = `${pct}%`;
    const historyProgress = document.getElementById("historyJobProgress");
    historyProgress.value = pct;
    historyProgress.textContent = `${pct}%`;
    const historyLink = document.getElementById("historyJobLink");
    historyLink.href = url;
    historyLink.querySelector("span").textContent = completed
      ? "ดูผล" : failed ? "ดูรายละเอียด" : "ดูสถานะ";
    const empty = document.getElementById("historyEmptyState");
    if (empty && !historyCard.hidden) empty.hidden = true;
  }
}

function notifyTrackedJobTerminal(job, previousStatus) {
  if (!isTerminalJob(job) || previousStatus === job.status) return;
  const noticeKey = `insightreview.jobNotice.${job.id}.${job.status}`;
  try {
    if (sessionStorage.getItem(noticeKey)) return;
    sessionStorage.setItem(noticeKey, "1");
  } catch (_) {}
  toast(
    job.status === "completed"
      ? "วิเคราะห์เสร็จแล้ว กดดูผลได้ทันที"
      : "งานวิเคราะห์ไม่สำเร็จ กดดูรายละเอียดได้",
    job.status === "completed" ? "ok" : "err",
    5200,
  );
}

function scheduleTrackedAnalysisPoll(delay = 1800) {
  clearTimeout(trackedAnalysisTimer);
  if (!trackedAnalysisJob || isTerminalJob(trackedAnalysisJob)) return;
  trackedAnalysisTimer = setTimeout(pollTrackedAnalysisJob, delay);
}

async function pollTrackedAnalysisJob() {
  const current = readTrackedAnalysisJob();
  if (!current || isTerminalJob(current) || document.getElementById("jobCard")) return;
  trackedAnalysisJob = current;
  try {
    const response = await fetch(
      current.apiUrl || `/api/jobs/${encodeURIComponent(current.id)}`,
      { headers: { "Accept": "application/json" }, cache: "no-store" },
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    const previousStatus = current.status;
    const updated = {
      ...current,
      ...payload,
      apiUrl: current.apiUrl || `/api/jobs/${encodeURIComponent(current.id)}`,
      statusUrl: current.statusUrl || `/jobs/${encodeURIComponent(current.id)}`,
      updatedAt: Date.now(),
    };
    trackedAnalysisErrors = 0;
    writeTrackedAnalysisJob(updated);
    renderTrackedAnalysisJob(updated);
    notifyTrackedJobTerminal(updated, previousStatus);
    scheduleTrackedAnalysisPoll(document.hidden ? 7000 : 1800);
  } catch (_) {
    trackedAnalysisErrors += 1;
    const reconnecting = {
      ...current,
      stageLabel: "กำลังเชื่อมต่อใหม่ งานยังไม่ถูกยกเลิก",
    };
    renderTrackedAnalysisJob(reconnecting);
    const trackerStage = document.getElementById("analysisTrackerStage");
    const historyStage = document.getElementById("historyJobStage");
    if (trackerStage) trackerStage.textContent = reconnecting.stageLabel;
    if (historyStage) historyStage.textContent = reconnecting.stageLabel;
    scheduleTrackedAnalysisPoll(Math.min(15000, 1800 * (2 ** Math.min(trackedAnalysisErrors, 3))));
  }
}

function registerTrackedAnalysisJob({ id, apiUrl, statusUrl }) {
  if (!id) return;
  const existing = readTrackedAnalysisJob();
  const job = existing?.id === id ? existing : {
    id,
    apiUrl: apiUrl || `/api/jobs/${encodeURIComponent(id)}`,
    statusUrl: statusUrl || `/jobs/${encodeURIComponent(id)}`,
    status: "queued",
    stage: "queued",
    progress: 0,
    createdAt: Date.now(),
  };
  writeTrackedAnalysisJob(job);
  renderTrackedAnalysisJob(job);
  scheduleTrackedAnalysisPoll(0);
}

function updateTrackedAnalysisJob(payload) {
  const current = readTrackedAnalysisJob();
  if (!current || !payload || current.id !== payload.id) return;
  const previousStatus = current.status;
  const updated = { ...current, ...payload, updatedAt: Date.now() };
  writeTrackedAnalysisJob(updated);
  renderTrackedAnalysisJob(updated);
  notifyTrackedJobTerminal(updated, previousStatus);
}

function clearTrackedAnalysisJob() {
  clearTimeout(trackedAnalysisTimer);
  trackedAnalysisJob = null;
  try { localStorage.removeItem(ACTIVE_ANALYSIS_JOB_KEY); } catch (_) {}
  renderTrackedAnalysisJob(null);
}

function initTrackedAnalysisJob() {
  trackedAnalysisJob = readTrackedAnalysisJob();
  renderTrackedAnalysisJob(trackedAnalysisJob);
  document.getElementById("analysisTrackerDismiss")?.addEventListener("click", clearTrackedAnalysisJob);
  scheduleTrackedAnalysisPoll(0);
}

window.AnalysisJobTracker = {
  register: registerTrackedAnalysisJob,
  update: updateTrackedAnalysisJob,
  clear: clearTrackedAnalysisJob,
};

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
  initTrackedAnalysisJob();

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

document.addEventListener("visibilitychange", () => {
  if (!document.hidden && trackedAnalysisJob && !isTerminalJob(trackedAnalysisJob)) {
    scheduleTrackedAnalysisPoll(0);
  }
});

window.addEventListener("storage", (event) => {
  if (event.key !== ACTIVE_ANALYSIS_JOB_KEY) return;
  trackedAnalysisJob = readTrackedAnalysisJob();
  renderTrackedAnalysisJob(trackedAnalysisJob);
  scheduleTrackedAnalysisPoll(0);
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
