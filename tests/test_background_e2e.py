"""Real demo pipeline -> background thread -> isolated SQLite smoke test."""

import os
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import app as webapp
from background_jobs import BackgroundJobRunner
from core import pipeline
from db import database


class TestBackgroundDemoEndToEnd(unittest.TestCase):
    def test_http_submission_completes_and_renders_dashboard(self):
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            database, "_DB_PATH", os.path.join(temp_dir, "e2e.db")
        ), mock.patch.object(
            config, "get_apify_token", return_value=""
        ), mock.patch.object(
            config, "get_use_model", return_value=False
        ), mock.patch.object(
            config, "get_extract_engine", return_value="rule"
        ), mock.patch.object(
            config, "get_max_reviews", return_value=30
        ):
            database.init_db()
            runner = BackgroundJobRunner(
                pipeline.run_analysis, database, max_workers=1, max_queued=0
            )
            try:
                webapp.app.config.update(TESTING=True)
                client = webapp.app.test_client()
                with client.session_transaction() as session:
                    session["_csrf_token"] = "e2e-csrf-token"
                with mock.patch.object(webapp, "job_runner", runner), mock.patch.object(
                    webapp.analysis_limiter, "consume", return_value=(True, 0)
                ):
                    response = client.post(
                        "/analyze",
                        data={
                            "url": "",
                            "engine": "lexicon",
                            "extract_engine": "rule",
                            "max_reviews": "30",
                            "_csrf_token": "e2e-csrf-token",
                        },
                    )
                    self.assertEqual(response.status_code, 302)
                    self.assertRegex(response.headers["Location"], r"^/jobs/[0-9a-f]{32}$")
                    job_id = response.headers["Location"].rsplit("/", 1)[-1]
                    self.assertEqual(client.get(response.headers["Location"]).status_code, 200)

                    deadline = time.monotonic() + 15
                    job = client.get(f"/api/jobs/{job_id}").get_json()
                    while job["status"] not in {"completed", "failed"}:
                        if time.monotonic() >= deadline:
                            self.fail("background demo job did not finish within 15 seconds")
                        time.sleep(0.02)
                        job = client.get(f"/api/jobs/{job_id}").get_json()

                    self.assertEqual(job["status"], "completed", job["error_message"])
                    self.assertEqual(job["stage"], "completed")
                    self.assertEqual(job["progress"], 100)
                    self.assertEqual(job["dashboard_url"], f"/dashboard/{job['analysis_id']}")
                    dashboard = client.get(job["dashboard_url"])
                    self.assertEqual(dashboard.status_code, 200)
                    self.assertIn("ครัวบ้านสวน".encode(), dashboard.data)
            finally:
                runner.shutdown()


if __name__ == "__main__":
    unittest.main()
