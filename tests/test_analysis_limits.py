import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app
import config


class TestAnalysisRequestGuards(unittest.TestCase):
    def setUp(self):
        app.app.config.update(TESTING=True)
        app.analysis_limiter.reset()
        self.client = app.app.test_client()
        with self.client.session_transaction() as session:
            session["_csrf_token"] = "analysis-token"

    def _post(self):
        return self.client.post(
            "/analyze",
            data={
                "url": "",
                "engine": "lexicon",
                "extract_engine": "rule",
                "max_reviews": "20",
                "_csrf_token": "analysis-token",
            },
        )

    def test_busy_gate_returns_503_without_consuming_quota(self):
        with (
            mock.patch.object(config, "get_apify_token", return_value=""),
            mock.patch.object(app.job_runner, "reserve", return_value=False),
            mock.patch.object(app.analysis_limiter, "consume") as consume,
            mock.patch.object(app.database, "create_job") as create,
        ):
            response = self._post()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["Retry-After"], "5")
        consume.assert_not_called()
        create.assert_not_called()

    def test_exhausted_quota_returns_429_and_releases_gate(self):
        with (
            mock.patch.object(config, "get_apify_token", return_value=""),
            mock.patch.object(app.job_runner, "reserve", return_value=True),
            mock.patch.object(app.job_runner, "cancel_reservation") as cancel,
            mock.patch.object(app.analysis_limiter, "consume", return_value=(False, 37)),
            mock.patch.object(app.database, "create_job") as create,
        ):
            response = self._post()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Retry-After"], "37")
        cancel.assert_called_once_with()
        create.assert_not_called()

    def test_reservation_is_released_when_job_creation_fails(self):
        with (
            mock.patch.object(config, "get_apify_token", return_value=""),
            mock.patch.object(app.job_runner, "reserve", return_value=True),
            mock.patch.object(app.job_runner, "cancel_reservation") as cancel,
            mock.patch.object(app.analysis_limiter, "consume", return_value=(True, 0)),
            mock.patch.object(app.database, "create_job", side_effect=RuntimeError("boom")),
        ):
            response = self._post()
        self.assertEqual(response.status_code, 302)
        cancel.assert_called_once_with()

    def test_allowed_request_is_queued_and_redirects_to_job_page(self):
        with (
            mock.patch.object(config, "get_apify_token", return_value=""),
            mock.patch.object(app.job_runner, "reserve", return_value=True),
            mock.patch.object(app.job_runner, "submit_reserved", return_value=True) as submit,
            mock.patch.object(app.analysis_limiter, "consume", return_value=(True, 0)),
            mock.patch.object(app.database, "create_job", return_value="job123") as create,
        ):
            response = self._post()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/jobs/job123")
        create.assert_called_once()
        source_url, owner_id = create.call_args.args
        self.assertEqual(source_url, "")
        self.assertTrue(owner_id.startswith("device:"))
        submit.assert_called_once_with(
            "job123", "", owner_id,
            {"use_model": False, "extract_engine": "rule", "max_reviews": 20},
        )


if __name__ == "__main__":
    unittest.main()
