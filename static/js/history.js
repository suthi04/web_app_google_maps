// history.js — search / sort / delete (confirm modal) / save toggle
// ใช้ฟังก์ชันกลางจาก common.js: toast(), confirmDialog()

(function () {
  const list = document.getElementById("histList");
  if (!list) return; // หน้า empty (ไม่มีข้อมูล)

  const onSavedPage = location.pathname === "/saved";

  /* ---------- Search ---------- */
  const search = document.getElementById("histSearch");
  const noResults = document.getElementById("noResults");

  function runSearch() {
    const q = (search.value || "").trim().toLowerCase();
    let visible = 0;
    list.querySelectorAll(".hist-card").forEach((card) => {
      const hit = card.dataset.name.includes(q);
      card.classList.toggle("hist-hidden", !hit);
      if (hit) visible++;
    });
    noResults.style.display = visible === 0 ? "" : "none";
    list.style.display = visible === 0 ? "none" : "";
  }
  search.addEventListener("input", runSearch);

  /* ---------- Sort ---------- */
  const sortBtn = document.getElementById("sortBtn");
  const sortMenu = document.getElementById("sortMenu");
  const sortLabel = document.getElementById("sortLabel");
  const SORT_TH = { newest: "ใหม่สุด", oldest: "เก่าสุด", pos: "บวกมากสุด", neg: "ลบมากสุด" };

  sortBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    sortMenu.classList.toggle("open");
  });
  document.addEventListener("click", () => sortMenu.classList.remove("open"));
  sortMenu.addEventListener("click", (e) => e.stopPropagation());

  function sortBy(mode) {
    const cards = [...list.querySelectorAll(".hist-card")];
    cards.sort((a, b) => {
      if (mode === "newest") return b.dataset.date.localeCompare(a.dataset.date);
      if (mode === "oldest") return a.dataset.date.localeCompare(b.dataset.date);
      if (mode === "pos") return (+b.dataset.pos) - (+a.dataset.pos);
      if (mode === "neg") return (+b.dataset.neg) - (+a.dataset.neg);
      return 0;
    });
    cards.forEach((c) => list.appendChild(c));
  }
  sortMenu.querySelectorAll(".mi").forEach((b) => {
    b.addEventListener("click", () => {
      sortMenu.querySelectorAll(".mi").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      sortLabel.textContent = SORT_TH[b.dataset.sort];
      sortBy(b.dataset.sort);
      sortMenu.classList.remove("open");
    });
  });

  /* ---------- Delete (with confirmation) ---------- */
  list.querySelectorAll(".del-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const id = btn.dataset.id;
      const name = btn.dataset.name;
      confirmDialog({
        title: "ลบผลการวิเคราะห์",
        body: `ต้องการลบ “${name}” ใช่หรือไม่? การลบนี้ไม่สามารถย้อนกลับได้`,
        okText: "ลบ",
        onOk: async () => {
          try {
            const res = await fetch(`/delete/${id}`, { method: "POST" });
            const j = await res.json();
            if (!j.deleted) throw new Error();
            const card = list.querySelector(`.hist-card[data-id="${id}"]`);
            card?.style.setProperty("transition", "opacity .2s, transform .2s");
            if (card) { card.style.opacity = "0"; card.style.transform = "translateX(-8px)"; }
            setTimeout(() => {
              card?.remove();
              toast("ลบเรียบร้อยแล้ว", "ok");
              if (!list.querySelector(".hist-card")) location.reload(); // โชว์ empty state
            }, 200);
          } catch {
            toast("ลบไม่สำเร็จ ลองใหม่อีกครั้ง", "err");
          }
        },
      });
    });
  });

  /* ---------- Save toggle ---------- */
  list.querySelectorAll(".save-toggle").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const id = btn.dataset.id;
      try {
        const res = await fetch(`/toggle-save/${id}`, { method: "POST" });
        const j = await res.json();
        const svg = btn.querySelector("svg");
        btn.classList.toggle("active", j.is_saved);
        svg.setAttribute("fill", j.is_saved ? "currentColor" : "none");

        const card = btn.closest(".hist-card");
        const hname = card.querySelector(".hname");
        let star = hname.querySelector(".saved-star");
        if (j.is_saved && !star) {
          hname.insertAdjacentHTML("beforeend",
            ' <svg class="saved-star" width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M6 4h12v16l-6-4-6 4V4z"/></svg>');
        } else if (!j.is_saved && star) {
          star.remove();
        }
        toast(j.is_saved ? "บันทึกเข้ารายการโปรดแล้ว" : "นำออกจากรายการโปรดแล้ว", "ok");

        // อยู่หน้า Saved แล้วเอาออก -> ลบการ์ดออกจากรายการ
        if (onSavedPage && !j.is_saved) {
          card.style.transition = "opacity .2s";
          card.style.opacity = "0";
          setTimeout(() => {
            card.remove();
            if (!list.querySelector(".hist-card")) location.reload();
          }, 200);
        }
      } catch {
        toast("ทำรายการไม่สำเร็จ", "err");
      }
    });
  });
})();
