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
  el.innerHTML =
    `<span class="ti"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor">${ICONS[type] || ICONS.ok}</svg></span>` +
    `<span>${message}</span>`;
  wrap.appendChild(el);
  requestAnimationFrame(() => el.classList.add("show"));
  setTimeout(() => {
    el.classList.remove("show");
    setTimeout(() => el.remove(), 300);
  }, ms);
}
window.toast = toast;

/* ---------- Confirm modal ---------- */
let _confirmCb = null;
function confirmDialog({ title, body, okText = "ลบ", onOk }) {
  const m = document.getElementById("confirmModal");
  if (!m) return;
  document.getElementById("confirmTitle").textContent = title || "ยืนยัน";
  document.getElementById("confirmBody").textContent = body || "";
  document.getElementById("confirmOk").textContent = okText;
  _confirmCb = onOk;
  m.classList.add("open");
}
window.confirmDialog = confirmDialog;

function _closeConfirm() {
  document.getElementById("confirmModal")?.classList.remove("open");
  _confirmCb = null;
}

/* ---------- Loading overlay ---------- */
function showLoading(on = true) {
  document.getElementById("loadingOverlay")?.classList.toggle("open", on);
}
window.showLoading = showLoading;

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
  });

  // mobile nav toggle
  const toggle = document.getElementById("navToggle");
  const scrim = document.getElementById("scrim");
  toggle?.addEventListener("click", () => document.body.classList.toggle("nav-open"));
  scrim?.addEventListener("click", () => document.body.classList.remove("nav-open"));

  initModelPickers();
});

/* ---------- Model picker (เลือกโมเดลในช่องวางลิงก์) ---------- */
// ตั้งค่า hidden input ตามที่ผู้ใช้เลือก + ไฮไลต์ตัวที่เลือก + อัปเดต label ปุ่ม
const _PICKER_LABEL = { model: "WangchanBERTa", lexicon: "Lexicon" };
function initModelPickers() {
  document.querySelectorAll("[data-picker]").forEach((picker) => {
    const btn = picker.querySelector("[data-picker-toggle]");
    const menu = picker.querySelector("[data-picker-menu]");
    const labelEl = picker.querySelector("[data-picker-label]");

    // ไฮไลต์ค่าเริ่มต้นจาก hidden input ของแต่ละ field
    function syncActive() {
      picker.querySelectorAll(".mi[data-field]").forEach((mi) => {
        const input = picker.querySelector(`input[name="${mi.dataset.field}"]`);
        mi.classList.toggle("active", input && input.value === mi.dataset.value);
      });
    }
    syncActive();

    btn?.addEventListener("click", (e) => {
      e.stopPropagation();
      menu.classList.toggle("open");
    });
    menu?.addEventListener("click", (e) => e.stopPropagation());

    picker.querySelectorAll(".mi[data-field]").forEach((mi) => {
      mi.addEventListener("click", () => {
        const input = picker.querySelector(`input[name="${mi.dataset.field}"]`);
        if (input) input.value = mi.dataset.value;
        if (mi.dataset.field === "engine" && labelEl) {
          labelEl.textContent = _PICKER_LABEL[mi.dataset.value] || mi.dataset.value;
        }
        syncActive();
      });
    });
  });
  // คลิกที่อื่น = ปิดเมนู picker ทุกตัว
  document.addEventListener("click", () =>
    document.querySelectorAll("[data-picker-menu].open").forEach((m) => m.classList.remove("open"))
  );
}
