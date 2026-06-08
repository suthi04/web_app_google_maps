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
});
