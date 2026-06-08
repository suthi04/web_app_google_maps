// dashboard.js — tabs (All/Keywords) + filter อารมณ์ + ปุ่ม save (+toast) + loading
// donut เป็น CSS ล้วน (ไม่ต้องวาดด้วย JS)

(function () {
  /* ---------- Tabs ---------- */
  const tabs = document.querySelectorAll(".seg .tab");
  const viewAll = document.getElementById("view-all");
  const viewKw = document.getElementById("view-keywords");
  tabs.forEach((t) => {
    t.addEventListener("click", () => {
      tabs.forEach((x) => x.classList.remove("active"));
      t.classList.add("active");
      const isAll = t.dataset.tab === "all";
      viewAll.style.display = isAll ? "" : "none";
      viewKw.style.display = isAll ? "none" : "";
    });
  });

  /* ---------- Filter dropdown ---------- */
  const filterBtn = document.getElementById("filterBtn");
  const filterMenu = document.getElementById("filterMenu");
  filterBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    filterMenu.classList.toggle("open");
  });
  document.addEventListener("click", () => filterMenu.classList.remove("open"));
  filterMenu.addEventListener("click", (e) => e.stopPropagation());

  function applyFilter(value) {
    document.querySelectorAll(".rev-row").forEach((row) => {
      row.style.display =
        value === "all" || row.dataset.sentiment === value ? "" : "none";
    });
    document.querySelectorAll(".chip").forEach((chip) => {
      chip.style.display =
        value === "all" || chip.dataset.sentiment === value ? "" : "none";
    });
  }
  filterMenu.querySelectorAll(".mi").forEach((b) => {
    b.addEventListener("click", () => {
      filterMenu.querySelectorAll(".mi").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      applyFilter(b.dataset.filter);
      filterMenu.classList.remove("open");
      if (b.dataset.filter !== "all") toast("กรองเฉพาะ " + b.textContent.trim(), "info", 1600);
    });
  });

  /* ---------- Save toggle ---------- */
  const saveBtn = document.getElementById("saveBtn");
  if (saveBtn) {
    saveBtn.addEventListener("click", async () => {
      const id = saveBtn.dataset.id;
      try {
        const res = await fetch(`/toggle-save/${id}`, { method: "POST" });
        const j = await res.json();
        const svg = saveBtn.querySelector("svg");
        const label = document.getElementById("saveLabel");
        svg.setAttribute("fill", j.is_saved ? "currentColor" : "none");
        label.textContent = j.is_saved ? "บันทึกแล้ว" : "บันทึก";
        saveBtn.dataset.saved = j.is_saved ? "1" : "0";
        toast(j.is_saved ? "บันทึกเข้ารายการโปรดแล้ว" : "นำออกจากรายการโปรดแล้ว", "ok");
      } catch (err) {
        toast("บันทึกไม่สำเร็จ ลองใหม่อีกครั้ง", "err");
      }
    });
  }

  /* ---------- Export dropdown ---------- */
  const exportBtn = document.getElementById("exportBtn");
  const exportMenu = document.getElementById("exportMenu");
  if (exportBtn) {
    exportBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      exportMenu.classList.toggle("open");
    });
    document.addEventListener("click", () => exportMenu.classList.remove("open"));
    exportMenu.addEventListener("click", () => toast("กำลังเตรียมไฟล์ดาวน์โหลด…", "info", 1600));
  }

  /* ---------- Analyze new (loading) ---------- */
  document.getElementById("analyzeForm")
    ?.addEventListener("submit", () => showLoading(true));
})();
