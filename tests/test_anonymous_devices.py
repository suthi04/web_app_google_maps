import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app
from db import database
from device_identity import COOKIE_NAME, owner_id_from_token


TOKEN_A = "a" * 64
TOKEN_B = "b" * 64
OWNER_A = owner_id_from_token(TOKEN_A)
OWNER_B = owner_id_from_token(TOKEN_B)


def _result():
    counts = {"positive": 1, "neutral": 0, "negative": 0}
    return {
        "store_name": "ร้านของเครื่องเอ",
        "source_url": "https://maps.google.com/?cid=anonymous-test",
        "total_reviews": 1,
        "fetched_reviews": 1,
        "engine": "Lexicon",
        "extract_engine": "rule",
        "distribution": {
            "counts": counts,
            "total": 1,
            "pct": {"positive": 100, "neutral": 0, "negative": 0},
        },
        "aspect_summary": {},
        "keywords": {},
        "insights": [],
        "reviews": [
            {
                "text": "อร่อย",
                "rating": 5,
                "review_date": None,
                "sentiment": "positive",
                "aspects": ["food"],
            }
        ],
    }


class TestAnonymousDeviceIsolation(unittest.TestCase):
    def setUp(self):
        app.app.config.update(TESTING=True)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path_patch = mock.patch.object(
            database, "_DB_PATH", os.path.join(self.temp_dir.name, "test.db")
        )
        self.path_patch.start()
        database.init_db()

        self.client_a = app.app.test_client()
        self.client_b = app.app.test_client()
        self.client_a.set_cookie(COOKIE_NAME, TOKEN_A)
        self.client_b.set_cookie(COOKIE_NAME, TOKEN_B)
        for client in (self.client_a, self.client_b):
            with client.session_transaction() as session:
                session["_csrf_token"] = "csrf"

        self.analysis_id = database.save_analysis(_result(), OWNER_A)
        self.job_id = database.create_job("", OWNER_A)

    def tearDown(self):
        self.path_patch.stop()
        self.temp_dir.cleanup()

    def test_new_browser_receives_persistent_httponly_device_cookie(self):
        client = app.app.test_client()
        response = client.get("/")
        cookie = response.headers.get("Set-Cookie", "")
        self.assertIn(f"{COOKIE_NAME}=", cookie)
        self.assertIn("Max-Age=34560000", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)

    def test_history_and_results_are_visible_only_to_the_owner(self):
        history_a = self.client_a.get("/history")
        history_b = self.client_b.get("/history")
        self.assertIn("ร้านของเครื่องเอ", history_a.get_data(as_text=True))
        self.assertNotIn("ร้านของเครื่องเอ", history_b.get_data(as_text=True))
        self.assertIn("เบราว์เซอร์นี้", history_a.get_data(as_text=True))

        self.assertEqual(
            self.client_a.get(f"/api/analysis/{self.analysis_id}").status_code,
            200,
        )
        self.assertEqual(
            self.client_b.get(f"/api/analysis/{self.analysis_id}").status_code,
            404,
        )
        self.assertEqual(
            self.client_a.get(f"/dashboard/{self.analysis_id}").status_code,
            200,
        )
        self.assertEqual(
            self.client_b.get(f"/dashboard/{self.analysis_id}").status_code,
            404,
        )
        for path in (
            f"/export/{self.analysis_id}/reviews.csv",
            f"/export/{self.analysis_id}/summary.csv",
            f"/export/{self.analysis_id}/labeling.json",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client_a.get(path).status_code, 200)
                self.assertEqual(self.client_b.get(path).status_code, 404)

    def test_job_status_is_visible_only_to_the_owner(self):
        self.assertEqual(self.client_a.get(f"/jobs/{self.job_id}").status_code, 200)
        self.assertEqual(self.client_b.get(f"/jobs/{self.job_id}").status_code, 404)
        self.assertEqual(
            self.client_b.get(f"/api/jobs/{self.job_id}").status_code, 404
        )

    def test_other_browser_cannot_save_or_delete_an_analysis(self):
        headers = {"X-CSRF-Token": "csrf"}
        self.assertEqual(
            self.client_b.post(
                f"/toggle-save/{self.analysis_id}", headers=headers
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client_b.post(
                f"/delete/{self.analysis_id}", headers=headers
            ).status_code,
            404,
        )
        self.assertIsNotNone(database.get_analysis(self.analysis_id, OWNER_A))

        response = self.client_b.post("/delete-all", headers=headers)
        self.assertEqual(response.get_json()["deleted_count"], 0)
        self.assertIsNotNone(database.get_analysis(self.analysis_id, OWNER_A))

        response = self.client_a.post("/delete-all", headers=headers)
        self.assertEqual(response.get_json()["deleted_count"], 1)
        self.assertIsNone(database.get_analysis(self.analysis_id, OWNER_A))


if __name__ == "__main__":
    unittest.main()
