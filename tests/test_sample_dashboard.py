"""The prepared example must remain usable when analysis dependencies fail."""
import json
from pathlib import Path
import unittest
from unittest import mock

import app


class TestSampleDashboard(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def test_sample_renders_without_analysis_services_or_database(self):
        with (
            mock.patch.object(app.pipeline, "run_analysis", side_effect=RuntimeError("model unavailable")) as run,
            mock.patch.object(app.pipeline.scraper, "fetch_reviews", side_effect=RuntimeError("Apify unavailable")) as fetch,
            mock.patch.object(app.database, "save_analysis") as save,
            mock.patch.object(app.database, "get_analysis") as get,
            mock.patch.object(app.database, "list_analyses", side_effect=RuntimeError("database unavailable")),
            mock.patch.object(app.audience_insights, "enrich_result", side_effect=RuntimeError("processing unavailable")) as enrich,
        ):
            response = self.client.get("/sample")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        for text in ("คุณกำลังดูข้อมูลตัวอย่าง", "ครัวบ้านสวน", "ไม่ใช่ผลของร้านที่คุณส่งวิเคราะห์", 'id="consumerView"', 'id="operatorView"', 'id="evidenceDrawer"'):
            self.assertIn(text, html)
        self.assertIn('data-sync-result-engine="0"', html)
        self.assertNotIn('id="saveBtn"', html)
        self.assertNotIn('id="exportBtn"', html)
        for operation in (run, fetch, save, get, enrich):
            operation.assert_not_called()

    def test_sample_contains_original_reviews_and_traceable_ids(self):
        root = Path(app.config.DATA_DIR)
        raw = json.loads((root / "sample_reviews.json").read_text(encoding="utf-8"))
        prepared = json.loads((root / "sample_analysis.json").read_text(encoding="utf-8"))
        self.assertEqual(prepared["store_name"], raw["store_name"])
        self.assertEqual(prepared["total_reviews"], len(prepared["reviews"]))
        self.assertEqual(prepared["total_reviews"], len(raw["reviews"]))
        self.assertEqual(sum(prepared["distribution"]["counts"].values()), prepared["total_reviews"])
        self.assertEqual(sum(prepared["distribution"]["pct"].values()), 100)
        ids = {r["review_id"] for r in prepared["reviews"]}
        self.assertEqual(len(ids), prepared["total_reviews"])
        for obsolete in (
            "insights", "practical_insights", "practical_insights_meta",
            "critical_issues",
        ):
            self.assertNotIn(obsolete, prepared)

        def check_evidence(value):
            if isinstance(value, dict):
                if "evidence_review_ids" in value:
                    self.assertTrue(set(value["evidence_review_ids"]) <= ids)
                for child in value.values():
                    check_evidence(child)
            elif isinstance(value, list):
                for child in value:
                    check_evidence(child)
        check_evidence(prepared)

    def test_failed_job_shows_sample_without_waiting_for_javascript(self):
        job = {"id": "example-failure", "status": "failed", "error_message": "โมเดลไม่พร้อม"}
        with mock.patch.object(app.database, "get_job", return_value=job):
            html = self.client.get("/jobs/example-failure").get_data(as_text=True)
        self.assertIn('href="/sample" class="btn btn-primary" id="jobSample" >', html)
        self.assertIn("โมเดลไม่พร้อม", html)
        self.assertNotIn("ออกจากหน้านี้ได้ ระบบจะวิเคราะห์ต่อ", html)

    def test_running_job_keeps_sample_hidden(self):
        job = {"id": "example-running", "status": "running", "error_message": None}
        with mock.patch.object(app.database, "get_job", return_value=job):
            html = self.client.get("/jobs/example-running").get_data(as_text=True)
        self.assertIn('id="jobSample" hidden', html)

    def test_server_errors_and_full_queue_offer_sample(self):
        for code in (429, 500, 503):
            with self.subTest(code=code), app.app.test_request_context("/"):
                app.bind_anonymous_device()
                html = app.render_template("error.html", code=str(code), title="ขัดข้อง", message="ลองใหม่")
                self.assertIn('href="/sample"', html)
                self.assertIn('class="btn btn-primary" href="/sample"', html)

    def test_redirected_errors_offer_sample_on_home(self):
        with self.client.session_transaction() as session:
            session["_flashes"] = [("err", "สร้างงานวิเคราะห์ไม่สำเร็จ กรุณาลองใหม่")]
        html = self.client.get("/").get_data(as_text=True)
        self.assertIn("ยังวิเคราะห์ไม่ได้?", html)
        self.assertIn('class="btn btn-primary" href="/sample"', html)


if __name__ == "__main__":
    unittest.main()
