// dashboard.js — view switch (Consumer/Entrepreneur) + All/Keywords + filter อารมณ์
// + show-more (แสดงรีวิวบางส่วน) + save (+toast) + export. donut เป็น CSS ล้วน.

(function () {
  /* ---------- View switch: ผู้บริโภค / ผู้ประกอบการ ---------- */
  const vtabs = document.querySelectorAll(".vtab");
  const views = {
    consumer: document.getElementById("view-consumer"),
    entrepreneur: document.getElementById("view-entrepreneur"),
  };
  vtabs.forEach((t) => {
    t.addEventListener("click", () => {
      vtabs.forEach((x) => x.classList.remove("active"));
      t.classList.add("active");
      const v = t.dataset.view;
      Object.entries(views).forEach(([k, el]) => {
        if (el) el.style.display = k === v ? "" : "none";
      });
    });
  });

  /* ---------- All / Keywords tabs ---------- */
  const tabs = document.querySelectorAll(".seg .tab");
  const viewAll = document.getElementById("view-all");
  const viewKw = document.getElementById("view-keywords");
  tabs.forEach((t) => {
    t.addEventListener("click", () => {
      tabs.forEach((x) => x.classList.remove("active"));
      t.classList.add("active");
      const isAll = t.dataset.tab === "all";
      if (viewAll) viewAll.style.display = isAll ? "" : "none";
      if (viewKw) viewKw.style.display = isAll ? "none" : "";
    });
  });

  /* ---------- Reviews: filter อารมณ์ + show-more (รวมกัน) ---------- */
  const CAP = 6; // แสดงกี่รีวิวก่อนต้องกด "แสดงเพิ่มเติม"
  const rows = [...document.querySelectorAll(".rev-row")];
  const chips = [...document.querySelectorAll(".chip")];
  const kwGroups = [...document.querySelectorAll(".kw-group")];
  const moreBtn = document.getElementById("showMoreReviews");
  const moreLabel = document.getElementById("showMoreLabel");
  const moreCaret = document.getElementById("showMoreCaret");
  let currentFilter = "all";
  let collapsed = true;

  function renderReviews() {
    let shown = 0;
    let matched = 0;
    rows.forEach((row) => {
      const ok = currentFilter === "all" || row.dataset.sentiment === currentFilter;
      if (!ok) {
        row.style.display = "none";
        return;
      }
      matched++;
      if (collapsed && shown >= CAP) {
        row.style.display = "none";
      } else {
        row.style.display = "";
        shown++;
      }
    });
    // ปุ่มแสดงเพิ่มเติม: โชว์เมื่อมีรีวิวมากกว่าที่แสดงอยู่ หรือกำลังขยายอยู่
    if (moreBtn) {
      const hasMore = matched > CAP;
      moreBtn.style.display = hasMore ? "" : "none";
      if (collapsed) {
        moreLabel.textContent = `แสดงเพิ่มเติม (${matched - shown} รีวิว)`;
        if (moreCaret) moreCaret.style.transform = "";
      } else {
        moreLabel.textContent = "ย่อรายการ";
        if (moreCaret) moreCaret.style.transform = "rotate(180deg)";
      }
    }
  }

  function applyKeywordFilter() {
    chips.forEach((chip) => {
      chip.style.display =
        currentFilter === "all" || chip.dataset.sentiment === currentFilter ? "" : "none";
    });
    kwGroups.forEach((g) => {
      const anyVisible = [...g.querySelectorAll(".chip")].some((c) => c.style.display !== "none");
      g.style.display = anyVisible ? "" : "none";
    });
  }

  moreBtn?.addEventListener("click", () => {
    collapsed = !collapsed;
    renderReviews();
  });

  renderReviews(); // ตั้งค่าเริ่มต้น (แสดงบางส่วน)

  /* ---------- Filter dropdown ---------- */
  const filterBtn = document.getElementById("filterBtn");
  const filterMenu = document.getElementById("filterMenu");
  filterBtn?.addEventListener("click", (e) => {
    e.stopPropagation();
    filterMenu.classList.toggle("open");
  });
  document.addEventListener("click", () => filterMenu?.classList.remove("open"));
  filterMenu?.addEventListener("click", (e) => e.stopPropagation());

  filterMenu?.querySelectorAll(".mi").forEach((b) => {
    b.addEventListener("click", () => {
      filterMenu.querySelectorAll(".mi").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      currentFilter = b.dataset.filter;
      collapsed = true; // เปลี่ยนตัวกรอง -> ยุบกลับ
      renderReviews();
      applyKeywordFilter();
      filterMenu.classList.remove("open");
      if (currentFilter !== "all") toast("กรองเฉพาะ " + b.textContent.trim(), "info", 1600);
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

  /* ---------- Regenerate narrative ด้วย Gemini (ไม่ดึงรีวิวซ้ำ) ---------- */
  const regenBtn = document.getElementById("regenBtn");
  regenBtn?.addEventListener("click", async () => {
    const id = regenBtn.dataset.id;
    regenBtn.disabled = true;
    const original = regenBtn.textContent;
    regenBtn.textContent = "กำลังเรียบเรียง…";
    try {
      const res = await fetch(`/regenerate/${id}`, { method: "POST" });
      const j = await res.json();
      if (j.ok && j.engine === "gemini") {
        toast("เรียบเรียงด้วย Gemini สำเร็จ กำลังรีเฟรช…", "ok");
        setTimeout(() => location.reload(), 800);
        return;
      }
      if (j.ok) {
        toast("Gemini ยังติดโควตา (ลองใหม่ภายหลัง หรือพรุ่งนี้เมื่อโควตารีเซ็ต)", "err", 4200);
      } else if (j.reason === "gemini_unavailable") {
        toast("Gemini ไม่พร้อมใช้ — ยังไม่ได้ตั้ง GEMINI_API_KEY", "err", 4200);
      } else {
        toast("สร้างเนื้อหาไม่สำเร็จ ลองใหม่อีกครั้ง", "err");
      }
    } catch (err) {
      toast("เชื่อมต่อไม่สำเร็จ ลองใหม่อีกครั้ง", "err");
    }
    regenBtn.disabled = false;
    regenBtn.textContent = original;
  });

  /* ---------- Analyze new (loading) ---------- */
  document.getElementById("analyzeForm")?.addEventListener("submit", () => showLoading(true));
})();
