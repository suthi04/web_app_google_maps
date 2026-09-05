(function () {
  const card = document.getElementById("jobCard");
  if (!card) return;

  const title = document.getElementById("jobTitle");
  const message = document.getElementById("jobMessage");
  const spinner = document.getElementById("jobSpinner");
  const progress = document.getElementById("jobProgress");
  const progressWrap = document.getElementById("jobProgressWrap");
  const stage = document.getElementById("jobStage");
  const percent = document.getElementById("jobPercent");
  const sample = document.getElementById("jobSample");
  const eyebrow = document.getElementById("jobEyebrow");
  const note = document.getElementById("jobBackgroundNote");
  const STAGE_LABELS = {
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
  let stopped = false;
  let consecutiveErrors = 0;
  let timerId = null;
  const BASE_DELAY = 1500;
  const MAX_DELAY = 15000;

  window.analysisTracker?.track({
    jobId: card.dataset.jobId,
    apiUrl: card.dataset.apiUrl,
    jobUrl: card.dataset.jobUrl,
  });

  function schedule(delay = BASE_DELAY) {
    if (stopped) return;
    clearTimeout(timerId);
    timerId = setTimeout(poll, delay);
  }

  function showFailure(text) {
    stopped = true;
    clearTimeout(timerId);
    if (sample) sample.hidden = false;
    if (eyebrow) eyebrow.textContent = "สถานะการวิเคราะห์";
    if (note) note.textContent = "ดูผลตัวอย่างที่เตรียมไว้ได้ทันที โดยไม่ต้องรอวิเคราะห์ใหม่";
    spinner?.classList.add("failed");
    progressWrap?.classList.add("failed");
    title.textContent = "วิเคราะห์ไม่สำเร็จ";
    message.textContent = text || "เกิดข้อผิดพลาด กรุณากลับหน้าแรกแล้วลองใหม่";
  }

  async function poll() {
    if (stopped) return;
    const controller = new AbortController();
    const requestTimeout = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch(card.dataset.apiUrl, {
        headers: { "Accept": "application/json" },
        cache: "no-store",
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const job = await response.json();
      consecutiveErrors = 0;
      if (sample) sample.hidden = true;
      if (note) note.textContent = "ออกจากหน้านี้ได้ ระบบจะวิเคราะห์ต่อและแสดงสถานะไว้ที่มุมหน้าจอ";
      const progressValue = Math.max(0, Math.min(100, Number(job.progress) || 0));
      if (progress) progress.value = progressValue;
      if (stage) stage.textContent = STAGE_LABELS[job.stage] || "กำลังประมวลผล";
      if (percent) percent.textContent = `${progressValue}%`;

      if (job.status === "completed" && job.analysis_id) {
        stopped = true;
        title.textContent = "วิเคราะห์เสร็จแล้ว";
        message.textContent = "กำลังเปิดผลลัพธ์…";
        window.analysisTracker?.clear();
        location.assign(job.dashboard_url || `/dashboard/${job.analysis_id}`);
        return;
      }
      if (job.status === "failed") {
        showFailure(job.error_message);
        return;
      }
      if (job.status === "running") {
        title.textContent = "กำลังวิเคราะห์รีวิว";
        message.textContent = "ระบบกำลังดึงและประมวลผลรีวิว หน้านี้จะเปิดผลลัพธ์ให้อัตโนมัติ";
      } else {
        title.textContent = "กำลังรอคิววิเคราะห์";
        message.textContent = "งานของคุณอยู่ในคิวและจะเริ่มโดยอัตโนมัติ";
      }
    } catch (_error) {
      consecutiveErrors += 1;
      if (sample) sample.hidden = false;
      if (note) note.textContent = "ระหว่างรอเชื่อมต่อใหม่ คุณเปิดดูข้อมูลตัวอย่างก่อนได้";
      title.textContent = "การเชื่อมต่อขัดข้องชั่วคราว";
      message.textContent = "ยังไม่ยกเลิกงาน ระบบกำลังลองเชื่อมต่อใหม่โดยอัตโนมัติ…";
      if (stage) stage.textContent = "กำลังเชื่อมต่อใหม่";
      const retryDelay = Math.min(
        MAX_DELAY,
        BASE_DELAY * (2 ** Math.min(consecutiveErrors - 1, 4))
      );
      schedule(retryDelay);
      return;
    } finally {
      clearTimeout(requestTimeout);
    }
    schedule();
  }

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && !stopped) schedule(0);
  });
  if (card.dataset.jobStatus === "failed") {
    showFailure(message.textContent.trim());
  } else {
    poll();
  }
})();
