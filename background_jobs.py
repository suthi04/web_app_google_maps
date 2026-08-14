"""Bounded in-process background runner for analysis jobs."""

import logging
from concurrent.futures import ThreadPoolExecutor

from request_limits import ConcurrencyGate


log = logging.getLogger(__name__)


class BackgroundJobRunner:
    def __init__(
        self,
        analysis_fn,
        database_module,
        max_workers: int = 1,
        max_queued: int = 10,
    ):
        self._analysis_fn = analysis_fn
        self._database = database_module
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, max_workers),
            thread_name_prefix="insightreview-analysis",
        )
        self._max_workers = max(1, max_workers)
        self._max_queued = max(0, max_queued)
        self._capacity = ConcurrencyGate(self._max_workers + self._max_queued)

    def reserve(self) -> bool:
        """Reserve one running/queued slot before charging request quota."""
        return self._capacity.try_acquire()

    def cancel_reservation(self) -> None:
        self._capacity.release()

    def submit_reserved(
        self,
        job_id: str,
        source_url: str,
        owner_id: str,
        analysis_options: dict | None = None,
    ) -> bool:
        """Submit a previously reserved job and release capacity when it ends."""
        try:
            future = self._executor.submit(
                self._run_job, job_id, source_url, owner_id, analysis_options
            )
        except RuntimeError:
            self._capacity.release()
            return False
        future.add_done_callback(lambda _future: self._capacity.release())
        return True

    def _run_job(
        self,
        job_id: str,
        source_url: str,
        owner_id: str,
        analysis_options: dict | None = None,
    ) -> None:
        if not self._database.mark_job_running(job_id):
            log.warning("Analysis job %s was not queued when worker started", job_id)
            return

        try:
            def report_progress(stage: str, progress: int) -> None:
                try:
                    self._database.update_job_progress(job_id, stage, progress)
                except Exception as exc:  # progress must never kill the analysis
                    log.warning(
                        "Could not update progress for job %s: %s", job_id, exc
                    )

            kwargs = {"progress_callback": report_progress}
            if analysis_options:
                kwargs.update(analysis_options)
            result = self._analysis_fn(source_url, **kwargs)
            if result.get("total_reviews", 0) == 0:
                self._database.mark_job_failed(
                    job_id,
                    "ไม่พบรีวิวภาษาไทยสำหรับวิเคราะห์ กรุณาลองร้านอื่นหรือเพิ่มจำนวนรีวิว",
                )
                return

            analysis_id = self._database.save_analysis(result, owner_id)
            if not self._database.mark_job_completed(job_id, analysis_id):
                log.error("Could not complete analysis job %s", job_id)
        except Exception as exc:  # noqa: BLE001 - worker must persist a safe failure
            log.exception("Analysis job %s failed: %s", job_id, exc)
            self._database.mark_job_failed(
                job_id,
                "วิเคราะห์ไม่สำเร็จ เนื่องจากบริการดึงรีวิวหรือโมเดลขัดข้อง กรุณาลองใหม่",
            )

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=not wait)

    def snapshot(self) -> dict:
        """Return queue capacity without exposing executor internals."""
        return {
            "max_workers": self._max_workers,
            "max_queued": self._max_queued,
            **self._capacity.snapshot(),
        }
