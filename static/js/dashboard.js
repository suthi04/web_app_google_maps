// dashboard.js — tabs (All/Keywords) + filter อารมณ์ + ปุ่ม save (+toast) + loading
// donut เป็น CSS ล้วน (ไม่ต้องวาดด้วย JS)

(function () {
  /* ---------- Audience personas ---------- */
  const personaTabs = [...document.querySelectorAll(".persona-tab")];
  const personaViews = {
    consumer: document.getElementById("consumerView"),
    operator: document.getElementById("operatorView"),
  };
  function setPersona(persona, updateUrl = true) {
    if (!personaViews[persona]) persona = "consumer";
    personaTabs.forEach((tab) => {
      const selected = tab.dataset.persona === persona;
      tab.classList.toggle("active", selected);
      tab.setAttribute("aria-selected", selected ? "true" : "false");
    });
    Object.entries(personaViews).forEach(([name, view]) => {
      view.hidden = name !== persona;
    });
    if (updateUrl) history.replaceState(null, "", `#${persona}`);
  }
  personaTabs.forEach((tab) => {
    tab.addEventListener("click", () => setPersona(tab.dataset.persona));
    tab.addEventListener("keydown", (event) => {
      if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
      event.preventDefault();
      const current = personaTabs.indexOf(tab);
      const delta = event.key === 'ArrowRight' ? 1 : -1;
      const next = personaTabs[(current + delta + personaTabs.length) % personaTabs.length];
      next.focus();
      next.click();
    });
  });
  setPersona(location.hash === "#operator" ? "operator" : "consumer", false);

  /* ---------- Tabs ---------- */
  const tabs = document.querySelectorAll(".seg .tab");
  const viewAll = document.getElementById("view-all");
  const viewKw = document.getElementById("view-keywords");
  tabs.forEach((t) => {
    t.addEventListener("click", () => {
      tabs.forEach((x) => {
        x.classList.remove("active");
        x.setAttribute("aria-selected", "false");
      });
      t.classList.add("active");
      t.setAttribute("aria-selected", "true");
      const isAll = t.dataset.tab === "all";
      viewAll.hidden = !isAll;
      viewKw.hidden = isAll;
    });
    t.addEventListener("keydown", (event) => {
      if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
      event.preventDefault();
      const current = [...tabs].indexOf(t);
      const delta = event.key === 'ArrowRight' ? 1 : -1;
      const next = tabs[(current + delta + tabs.length) % tabs.length];
      next.focus();
      next.click();
    });
  });

  /* ---------- Filter dropdown ---------- */
  const filterBtn = document.getElementById("filterBtn");
  const filterMenu = document.getElementById("filterMenu");
  filterMenu.querySelectorAll(".mi").forEach((item) => {
    item.setAttribute("role", "menuitemradio");
    item.setAttribute("aria-checked", item.classList.contains("active") ? "true" : "false");
  });
  function setFilterOpen(open) {
    filterMenu.classList.toggle("open", open);
    filterBtn.setAttribute("aria-expanded", open ? "true" : "false");
  }
  filterBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    setFilterOpen(!filterMenu.classList.contains("open"));
  });
  document.addEventListener("click", () => setFilterOpen(false));
  filterMenu.addEventListener("click", (e) => e.stopPropagation());

  function applyFilter(value) {
    document.querySelectorAll(".rev-row").forEach((row) => {
      const matches = value === "all" || row.dataset.sentiment === value;
      row.hidden = !matches;
    });
    document.querySelectorAll(".chip").forEach((chip) => {
      const matches = value === "all" || chip.dataset.sentiment === value;
      chip.hidden = !matches;
    });
    // ซ่อนกลุ่มคำสำคัญที่ไม่เหลือ chip หลังกรอง (กันหัวข้อกลุ่มลอยว่าง)
    document.querySelectorAll(".kw-group").forEach((g) => {
      const anyVisible = [...g.querySelectorAll(".chip")].some(
        (c) => !c.hidden
      );
      g.hidden = !anyVisible;
    });
  }
  filterMenu.querySelectorAll(".mi").forEach((b) => {
    b.addEventListener("click", () => {
      filterMenu.querySelectorAll(".mi").forEach((x) => {
        x.classList.remove("active");
        x.setAttribute("aria-checked", "false");
      });
      b.classList.add("active");
      b.setAttribute("aria-checked", "true");
      applyFilter(b.dataset.filter);
      setFilterOpen(false);
      if (b.dataset.filter !== "all") toast("กรองเฉพาะ " + b.textContent.trim(), "info", 1600);
    });
  });

  applyFilter("all");

  /* ---------- Consumer review explorer ---------- */
  const consumerReviewList = document.getElementById("consumerReviewList");
  const consumerReviewCards = [...document.querySelectorAll(".consumer-review-card")];
  const consumerReviewSearch = document.getElementById("consumerReviewSearch");
  const consumerReviewEmpty = document.getElementById("consumerReviewEmpty");
  const consumerReviewVisibleCount = document.getElementById("consumerReviewVisibleCount");
  const consumerFilterButtons = [...document.querySelectorAll("[data-consumer-filter]")];
  let consumerSentimentFilter = "all";

  function setHighlightedText(element, text, query) {
    element.textContent = "";
    const needle = (query || "").trim();
    if (!needle) {
      element.textContent = text;
      return;
    }
    const index = text.toLocaleLowerCase("th").indexOf(needle.toLocaleLowerCase("th"));
    if (index < 0) {
      element.textContent = text;
      return;
    }
    element.append(document.createTextNode(text.slice(0, index)));
    const mark = document.createElement("mark");
    mark.textContent = text.slice(index, index + needle.length);
    element.append(mark, document.createTextNode(text.slice(index + needle.length)));
  }

  function applyConsumerReviewFilter() {
    if (!consumerReviewList) return;
    const query = (consumerReviewSearch?.value || "").trim().toLocaleLowerCase("th");
    let visibleCount = 0;
    consumerReviewCards.forEach((card) => {
      const matchesSentiment = consumerSentimentFilter === "all"
        || card.dataset.sentiment === consumerSentimentFilter;
      const matchesSearch = !query
        || (card.dataset.reviewText || "").toLocaleLowerCase("th").includes(query);
      card.hidden = !matchesSentiment || !matchesSearch;
      card.classList.remove("evidence-focus");
      setHighlightedText(
        card.querySelector(".consumer-review-text"),
        card.dataset.reviewText || "",
        query,
      );
      if (!card.hidden) visibleCount += 1;
    });
    if (consumerReviewEmpty) consumerReviewEmpty.hidden = visibleCount > 0;
    if (consumerReviewVisibleCount) {
      consumerReviewVisibleCount.textContent = `แสดง ${visibleCount} จาก ${consumerReviewCards.length} รีวิว`;
    }
  }

  consumerFilterButtons.forEach((button) => {
    button.addEventListener("click", () => {
      consumerSentimentFilter = button.dataset.consumerFilter;
      consumerFilterButtons.forEach((item) => {
        const active = item === button;
        item.classList.toggle("active", active);
        item.setAttribute("aria-pressed", active ? "true" : "false");
      });
      applyConsumerReviewFilter();
    });
  });
  consumerReviewSearch?.addEventListener("input", applyConsumerReviewFilter);
  applyConsumerReviewFilter();

  /* ---------- Evidence drawer ---------- */
  const evidenceShell = document.getElementById("evidenceDrawer");
  const evidenceDrawerList = document.getElementById("evidenceDrawerList");
  const evidenceDrawerTitle = document.getElementById("evidenceDrawerTitle");
  const evidenceDrawerMeta = document.getElementById("evidenceDrawerMeta");
  const evidenceCloseBtn = document.getElementById("evidenceCloseBtn");
  const evidenceJumpBtn = document.getElementById("evidenceJumpBtn");
  let activeEvidenceIds = [];
  let activeEvidenceQuery = "";
  let evidenceReturnFocus = null;

  function parseEvidenceIds(value) {
    return [...new Set((value || "").split(",").map((id) => id.trim()).filter(Boolean))];
  }

  function closeEvidence({ restoreFocus = true } = {}) {
    if (!evidenceShell || evidenceShell.hidden) return;
    evidenceShell.classList.remove("open");
    evidenceShell.hidden = true;
    document.body.classList.remove("evidence-open");
    if (restoreFocus) evidenceReturnFocus?.focus();
  }

  function evidenceCardClone(source, query) {
    const clone = source.cloneNode(true);
    clone.removeAttribute("id");
    clone.removeAttribute("hidden");
    clone.classList.add("evidence-review-card");
    setHighlightedText(
      clone.querySelector(".consumer-review-text"),
      source.dataset.reviewText || "",
      query,
    );
    return clone;
  }

  function openEvidence(trigger) {
    if (!evidenceShell || trigger.disabled) return;
    const ids = parseEvidenceIds(trigger.dataset.evidence);
    if (!ids.length) return;
    activeEvidenceIds = ids;
    activeEvidenceQuery = (trigger.dataset.evidenceQuery || "").trim();
    evidenceReturnFocus = trigger;
    evidenceDrawerList.replaceChildren();
    evidenceDrawerList.scrollTop = 0;
    ids.forEach((id) => {
      const source = document.getElementById(`consumer-review-${id}`);
      if (source) evidenceDrawerList.append(evidenceCardClone(source, activeEvidenceQuery));
    });
    evidenceDrawerTitle.textContent = activeEvidenceQuery
      ? `หลักฐาน: “${activeEvidenceQuery}”`
      : "รีวิวอ้างอิง";
    evidenceDrawerMeta.textContent = `อ้างอิง ${ids.length} รีวิวไม่ซ้ำ · ${ids.join(", ")}`;
    evidenceShell.hidden = false;
    evidenceShell.classList.add("open");
    document.body.classList.add("evidence-open");
    evidenceCloseBtn?.focus();
  }

  document.querySelectorAll(".evidence-trigger, .evidence-link").forEach((trigger) => {
    trigger.addEventListener("click", () => openEvidence(trigger));
  });
  document.querySelectorAll("[data-evidence-close]").forEach((button) => {
    button.addEventListener("click", () => closeEvidence());
  });
  evidenceJumpBtn?.addEventListener("click", () => {
    const focusIds = new Set(activeEvidenceIds);
    closeEvidence({ restoreFocus: false });
    setPersona("consumer");
    consumerSentimentFilter = "all";
    consumerFilterButtons.forEach((button) => {
      button.classList.toggle("active", button.dataset.consumerFilter === "all");
    });
    if (consumerReviewSearch) consumerReviewSearch.value = "";
    applyConsumerReviewFilter();
    consumerReviewCards.forEach((card) => {
      const focused = focusIds.has(card.dataset.reviewId);
      card.classList.toggle("evidence-focus", focused);
      if (focused) {
        setHighlightedText(
          card.querySelector(".consumer-review-text"),
          card.dataset.reviewText || "",
          activeEvidenceQuery,
        );
      }
    });
    const first = document.getElementById(`consumer-review-${activeEvidenceIds[0]}`);
    first?.scrollIntoView({ behavior: "smooth", block: "center" });
  });

  /* ---------- Save toggle ---------- */
  const saveBtn = document.getElementById("saveBtn");
  if (saveBtn) {
    saveBtn.addEventListener("click", async () => {
      const id = saveBtn.dataset.id;
      try {
        const res = await fetch(`/toggle-save/${id}`, {
          method: "POST",
          headers: csrfHeaders(),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const j = await res.json();
        const svg = saveBtn.querySelector("svg");
        const label = document.getElementById("saveLabel");
        svg.setAttribute("fill", j.is_saved ? "currentColor" : "none");
        label.textContent = j.is_saved ? "บันทึกแล้ว" : "บันทึก";
        saveBtn.dataset.saved = j.is_saved ? "1" : "0";
        saveBtn.setAttribute("aria-pressed", j.is_saved ? "true" : "false");
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
    exportMenu.querySelectorAll("a").forEach((item) => item.setAttribute("role", "menuitem"));
    function setExportOpen(open) {
      exportMenu.classList.toggle("open", open);
      exportBtn.setAttribute("aria-expanded", open ? "true" : "false");
    }
    exportBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      setExportOpen(!exportMenu.classList.contains("open"));
    });
    document.addEventListener("click", () => setExportOpen(false));
    exportMenu.addEventListener("click", () => {
      setExportOpen(false);
      toast("กำลังเตรียมไฟล์ดาวน์โหลด…", "info", 1600);
    });
  }
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    closeEvidence();
    setFilterOpen(false);
    if (exportBtn) {
      exportMenu.classList.remove("open");
      exportBtn.setAttribute("aria-expanded", "false");
    }
  });
})();
