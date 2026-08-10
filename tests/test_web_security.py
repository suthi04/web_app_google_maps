import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app
import config


class TestWebSecurity(unittest.TestCase):
    def setUp(self):
        app.app.config.update(TESTING=True)
        self.client = app.app.test_client()

    def _set_token(self, token="test-csrf-token"):
        with self.client.session_transaction() as session:
            session["_csrf_token"] = token
        return token

    def test_page_renders_csrf_meta_and_form_token(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'name="csrf-token"', response.data)
        self.assertIn(b'name="_csrf_token"', response.data)

    def test_post_without_token_is_rejected_before_route(self):
        with mock.patch.object(config, "save_settings") as save:
            response = self.client.post("/settings", data={"engine": "lexicon"})
        self.assertEqual(response.status_code, 400)
        save.assert_not_called()

    def test_form_token_allows_state_changing_route(self):
        token = self._set_token()
        with mock.patch.object(config, "save_settings") as save:
            response = self.client.post(
                "/settings",
                data={
                    "engine": "lexicon",
                    "extract_engine": "rule",
                    "max_reviews": "20",
                    "_csrf_token": token,
                },
            )
        self.assertEqual(response.status_code, 302)
        save.assert_called_once()

    def test_header_token_allows_fetch_style_request_and_missing_is_404(self):
        token = self._set_token()
        with mock.patch.object(app.database, "toggle_saved", return_value=None):
            response = self.client.post(
                "/toggle-save/999999",
                headers={"X-CSRF-Token": token},
            )
        self.assertEqual(response.status_code, 404)

    def test_delete_all_requires_csrf_and_returns_deleted_count(self):
        with mock.patch.object(app.database, "delete_all_analyses") as delete_all:
            response = self.client.post("/delete-all")
            self.assertEqual(response.status_code, 400)
            delete_all.assert_not_called()

            token = self._set_token()
            delete_all.return_value = 3
            response = self.client.post(
                "/delete-all", headers={"X-CSRF-Token": token}
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(), {"deleted": True, "deleted_count": 3}
        )
        delete_all.assert_called_once_with()

    def test_security_headers_are_present_on_success_and_error(self):
        for path in ("/", "/does-not-exist"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
                self.assertEqual(response.headers["X-Frame-Options"], "DENY")
                self.assertEqual(response.headers["Referrer-Policy"], "same-origin")
                self.assertIn("geolocation=()", response.headers["Permissions-Policy"])
                self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
                self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_inline_analysis_controls_disclose_llm_data_transfer(self):
        response = self.client.get("/")
        self.assertIn("Google Gemini".encode(), response.data)
        self.assertIn("ส่งไปประมวลผล".encode(), response.data)

    def test_healthcheck_reports_database_state(self):
        with mock.patch.object(app.database, "healthcheck", return_value=True):
            response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")
        self.assertIn("jobs", response.get_json())
        self.assertIn("available", response.get_json()["jobs"])

        with mock.patch.object(
            app.database, "healthcheck", side_effect=RuntimeError("db down")
        ):
            response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["status"], "unhealthy")

    def test_api_missing_resource_returns_json_error(self):
        with mock.patch.object(app.database, "get_analysis", return_value=None):
            response = self.client.get("/api/analysis/999999")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json(), {"error": "not_found", "status": 404})

    def test_overlong_analysis_url_is_rejected_before_pipeline(self):
        token = self._set_token()
        with mock.patch.object(app.pipeline, "run_analysis") as run:
            response = self.client.post(
                "/analyze",
                data={"url": "https://maps.google.com/" + "x" * 2100,
                      "_csrf_token": token},
            )
        self.assertEqual(response.status_code, 302)
        run.assert_not_called()

    def test_request_body_larger_than_limit_is_rejected(self):
        token = self._set_token()
        response = self.client.post(
            "/settings",
            data={"_csrf_token": token, "oversized": "x" * (1024 * 1024)},
        )
        self.assertEqual(response.status_code, 413)


if __name__ == "__main__":
    unittest.main()
