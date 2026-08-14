import os
import sys
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from background_jobs import BackgroundJobRunner
from request_limits import ConcurrencyGate


OWNER = "device:test"


class _ImmediateFuture:
    def add_done_callback(self, callback):
        callback(self)


class _ImmediateExecutor:
    def submit(self, fn, *args):
        fn(*args)
        return _ImmediateFuture()


class _BrokenExecutor:
    def submit(self, fn, *args):
        raise RuntimeError("executor stopped")


class TestBackgroundJobRunner(unittest.TestCase):
    def _runner(self, analysis_fn=None):
        database = mock.Mock()
        database.mark_job_running.return_value = True
        database.mark_job_completed.return_value = True
        database.mark_job_failed.return_value = True
        database.save_analysis.return_value = 77
        runner = BackgroundJobRunner(
            analysis_fn or (
                lambda _url, progress_callback=None: {"total_reviews": 1}
            ),
            database,
            max_workers=1,
            max_queued=0,
        )
        return runner, database

    def test_successful_job_saves_analysis_and_completes(self):
        runner, database = self._runner()
        try:
            runner._run_job("job", "url", OWNER)
        finally:
            runner.shutdown()
        database.save_analysis.assert_called_once_with({"total_reviews": 1}, OWNER)
        database.mark_job_completed.assert_called_once_with("job", 77)
        database.mark_job_failed.assert_not_called()

    def test_empty_review_result_becomes_user_visible_failure(self):
        runner, database = self._runner(
            lambda _url, progress_callback=None: {"total_reviews": 0}
        )
        try:
            runner._run_job("job", "url", OWNER)
        finally:
            runner.shutdown()
        database.save_analysis.assert_not_called()
        database.mark_job_failed.assert_called_once()

    def test_worker_exception_is_persisted_without_leaking_exception_text(self):
        runner, database = self._runner(
            lambda _url, progress_callback=None: (_ for _ in ()).throw(
                RuntimeError("private detail")
            )
        )
        try:
            runner._run_job("job", "url", OWNER)
        finally:
            runner.shutdown()
        message = database.mark_job_failed.call_args.args[1]
        self.assertNotIn("private detail", message)

    def test_non_queued_job_is_not_processed(self):
        analysis = mock.Mock(return_value={"total_reviews": 1})
        runner, database = self._runner(analysis)
        database.mark_job_running.return_value = False
        try:
            runner._run_job("job", "url", OWNER)
        finally:
            runner.shutdown()
        analysis.assert_not_called()

    def test_pipeline_progress_is_forwarded_to_database(self):
        def analysis(_url, progress_callback=None):
            progress_callback("preprocessing", 30)
            progress_callback("sentiment", 50)
            return {"total_reviews": 1}

        runner, database = self._runner(analysis)
        try:
            runner._run_job("job", "url", OWNER)
        finally:
            runner.shutdown()
        self.assertEqual(
            database.update_job_progress.call_args_list,
            [
                mock.call("job", "preprocessing", 30),
                mock.call("job", "sentiment", 50),
            ],
        )

    def test_completed_submission_releases_reserved_capacity(self):
        runner, _database = self._runner()
        original_executor = runner._executor
        runner._executor = _ImmediateExecutor()
        original_executor.shutdown()

        self.assertTrue(runner.reserve())
        self.assertTrue(runner.submit_reserved("job", "url", OWNER))
        self.assertTrue(runner.reserve())
        runner.cancel_reservation()

    def test_failed_submission_releases_reserved_capacity(self):
        runner, _database = self._runner()
        original_executor = runner._executor
        runner._executor = _BrokenExecutor()
        original_executor.shutdown()

        self.assertTrue(runner.reserve())
        self.assertFalse(runner.submit_reserved("job", "url", OWNER))
        self.assertTrue(runner.reserve())
        runner.cancel_reservation()

    def test_snapshot_exposes_worker_and_queue_capacity(self):
        runner, _database = self._runner()
        try:
            self.assertEqual(
                runner.snapshot(),
                {
                    "max_workers": 1,
                    "max_queued": 0,
                    "capacity": 1,
                    "inflight": 0,
                    "available": 1,
                },
            )
        finally:
            runner.shutdown()

    def test_per_job_options_are_forwarded_to_analysis_function(self):
        analysis = mock.Mock(return_value={"total_reviews": 1})
        runner, _database = self._runner(analysis)
        try:
            runner._run_job(
                "job", "url", OWNER,
                {"use_model": False, "extract_engine": "rule", "max_reviews": 20},
            )
        finally:
            runner.shutdown()
        analysis.assert_called_once()
        kwargs = analysis.call_args.kwargs
        self.assertFalse(kwargs["use_model"])
        self.assertEqual(kwargs["extract_engine"], "rule")
        self.assertEqual(kwargs["max_reviews"], 20)
        self.assertTrue(callable(kwargs["progress_callback"]))

    def test_three_workers_can_run_three_jobs_at_the_same_time(self):
        state = {"active": 0, "maximum": 0}
        state_lock = threading.Lock()
        all_started = threading.Event()
        release = threading.Event()

        def analysis(_url, progress_callback=None):
            with state_lock:
                state["active"] += 1
                state["maximum"] = max(state["maximum"], state["active"])
                if state["active"] == 3:
                    all_started.set()
            release.wait(2)
            with state_lock:
                state["active"] -= 1
            return {"total_reviews": 1}

        runner, database = self._runner(analysis)
        original_executor = runner._executor
        runner._executor = ThreadPoolExecutor(max_workers=3)
        runner._max_workers = 3
        runner._capacity = ConcurrencyGate(3)
        original_executor.shutdown()
        try:
            for index in range(3):
                self.assertTrue(runner.reserve())
                self.assertTrue(
                    runner.submit_reserved(f"job-{index}", "url", OWNER)
                )
            self.assertTrue(all_started.wait(1), "three jobs did not start together")
            self.assertEqual(runner.snapshot()["inflight"], 3)
            release.set()
            deadline = time.monotonic() + 2
            while database.mark_job_completed.call_count < 3:
                if time.monotonic() >= deadline:
                    self.fail("three concurrent jobs did not finish")
                time.sleep(0.01)
        finally:
            release.set()
            runner.shutdown()

        self.assertEqual(state["maximum"], 3)


if __name__ == "__main__":
    unittest.main()
