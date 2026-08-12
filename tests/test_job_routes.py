import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app


class TestJobRoutes(unittest.TestCase):
    def setUp(self):
        app.app.config.update(TESTING=True)
        self.client = app.app.test_client()

    def test_queued_job_page_renders_polling_client(self):
        job = {"id": "abc123", "status": "queued", "analysis_id": None,
               "error_message": None}
        with mock.patch.object(app.database, "get_job", return_value=job):
            response = self.client.get("/jobs/abc123")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"/api/jobs/abc123", response.data)
        self.assertIn(b"js/job.js", response.data)
        self.assertIn(b"20260812-evidence-chart1", response.data)
        self.assertIn(b'data-job-id="abc123"', response.data)
        self.assertIn(b'data-job-url="/jobs/abc123"', response.data)
        self.assertIn("ออกจากหน้านี้ได้ ระบบจะวิเคราะห์ต่อ".encode(), response.data)

    def test_every_page_has_persistent_analysis_tracker(self):
        response = self.client.get("/")
        self.assertIn(b'id="analysisTracker"', response.data)
        self.assertIn(b'id="analysisTrackerProgress"', response.data)
        self.assertIn(b'id="analysisTrackerLink"', response.data)

    def test_common_client_persists_and_polls_active_job(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "static", "js", "common.js"), encoding="utf-8") as handle:
            script = handle.read()
        self.assertIn("insightreview.activeAnalysisJob.v1", script)
        self.assertIn("_pollAnalysisTracker", script)
        self.assertIn("วิเคราะห์เสร็จแล้ว เปิดดูผลลัพธ์ได้เลย", script)
        self.assertIn('window.addEventListener("storage"', script)

    def test_common_client_syncs_picker_with_engine_used_by_result(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "static", "js", "common.js"), encoding="utf-8") as handle:
            script = handle.read()
        self.assertIn('form.dataset.syncResultEngine === "1"', script)
        self.assertIn("saved.extract_engine = actualEngine", script)

    def test_completed_job_page_redirects_to_dashboard(self):
        job = {"id": "abc123", "status": "completed", "analysis_id": 42,
               "error_message": None}
        with mock.patch.object(app.database, "get_job", return_value=job):
            response = self.client.get("/jobs/abc123")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/dashboard/42")

    def test_job_api_returns_persisted_status(self):
        job = {"id": "abc123", "status": "running", "analysis_id": None,
               "error_message": None, "stage": "sentiment", "progress": 50}
        with mock.patch.object(app.database, "get_job", return_value=job):
            response = self.client.get("/api/jobs/abc123")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "running")
        self.assertEqual(response.get_json()["progress"], 50)

    def test_completed_job_api_includes_server_generated_dashboard_url(self):
        job = {"id": "abc123", "status": "completed", "analysis_id": 42,
               "error_message": None, "stage": "completed", "progress": 100}
        with mock.patch.object(app.database, "get_job", return_value=job):
            response = self.client.get("/api/jobs/abc123")
        self.assertEqual(response.get_json()["dashboard_url"], "/dashboard/42")

    def test_missing_job_api_returns_json_404(self):
        with mock.patch.object(app.database, "get_job", return_value=None):
            response = self.client.get("/api/jobs/missing")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "not_found")


if __name__ == "__main__":
    unittest.main()
