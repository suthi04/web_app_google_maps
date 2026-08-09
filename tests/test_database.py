import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import database


def _analysis_result():
    return {
        "store_name": "ร้านทดสอบ",
        "source_url": "https://maps.google.com/?cid=test",
        "total_reviews": 1,
        "distribution": {
            "count": {"positive": 1, "neutral": 0, "negative": 0},
            "pct": {"positive": 100, "neutral": 0, "negative": 0},
        },
        "reviews": [],
    }


class TestDatabaseLifecycle(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp_dir.name, "test.db")
        self.path_patch = mock.patch.object(database, "_DB_PATH", self.path)
        self.path_patch.start()
        database.init_db()

    def tearDown(self):
        self.path_patch.stop()
        self.temp_dir.cleanup()

    def test_save_get_toggle_and_delete_round_trip(self):
        aid = database.save_analysis(_analysis_result())
        loaded = database.get_analysis(aid)
        self.assertEqual(loaded["store_name"], "ร้านทดสอบ")
        self.assertFalse(loaded["is_saved"])

        self.assertTrue(database.toggle_saved(aid))
        self.assertTrue(database.get_analysis(aid)["is_saved"])
        self.assertTrue(database.delete_analysis(aid))
        self.assertIsNone(database.get_analysis(aid))

    def test_missing_record_is_distinct_from_unsaved_record(self):
        self.assertIsNone(database.toggle_saved(999999))
        self.assertFalse(database.delete_analysis(999999))

    def test_connection_is_closed_after_context(self):
        with database._conn() as connection:
            connection.execute("SELECT 1").fetchone()
        with self.assertRaises(database.sqlite3.ProgrammingError):
            connection.execute("SELECT 1")

    def test_healthcheck_queries_database(self):
        self.assertTrue(database.healthcheck())

    def test_job_lifecycle(self):
        job_id = database.create_job("https://maps.google.com/maps")
        queued = database.get_job(job_id)
        self.assertEqual(queued["status"], "queued")
        self.assertEqual(queued["stage"], "queued")
        self.assertEqual(queued["progress"], 0)

        self.assertTrue(database.mark_job_running(job_id))
        self.assertTrue(database.update_job_progress(job_id, "sentiment", 50))
        aid = database.save_analysis(_analysis_result())
        self.assertTrue(database.mark_job_completed(job_id, aid))

        completed = database.get_job(job_id)
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["analysis_id"], aid)
        self.assertEqual(completed["stage"], "completed")
        self.assertEqual(completed["progress"], 100)
        self.assertIsNotNone(completed["finished_at"])

    def test_job_transitions_are_conditional(self):
        job_id = database.create_job("")
        self.assertFalse(database.mark_job_completed(job_id, 1))
        self.assertTrue(database.mark_job_failed(job_id, "failed"))
        self.assertFalse(database.mark_job_running(job_id))
        self.assertFalse(database.mark_job_failed(job_id, "again"))
        with self.assertRaises(ValueError):
            database.update_job_progress(job_id, "unknown-stage", 20)

    def test_init_db_migrates_legacy_job_table(self):
        with database._conn() as connection:
            connection.execute("DROP TABLE analysis_job")
            connection.execute(
                """CREATE TABLE analysis_job (
                       id TEXT PRIMARY KEY, status TEXT NOT NULL,
                       source_url TEXT, created_at TEXT NOT NULL,
                       started_at TEXT, finished_at TEXT,
                       analysis_id INTEGER, error_message TEXT
                   )"""
            )
        database.init_db()
        with database._conn() as connection:
            columns = {
                row["name"] for row in connection.execute(
                    "PRAGMA table_info(analysis_job)"
                )
            }
        self.assertIn("stage", columns)
        self.assertIn("progress", columns)

    def test_recover_interrupted_jobs_marks_only_unfinished(self):
        queued = database.create_job("")
        running = database.create_job("")
        completed = database.create_job("")
        database.mark_job_running(running)
        database.mark_job_running(completed)
        aid = database.save_analysis(_analysis_result())
        database.mark_job_completed(completed, aid)

        self.assertEqual(database.recover_interrupted_jobs(), 2)
        self.assertEqual(database.get_job(queued)["status"], "failed")
        self.assertEqual(database.get_job(running)["status"], "failed")
        self.assertEqual(database.get_job(completed)["status"], "completed")

    def test_prune_finished_jobs_preserves_analysis_and_recent_jobs(self):
        old_job = database.create_job("")
        recent_job = database.create_job("")
        for job_id in (old_job, recent_job):
            database.mark_job_running(job_id)
        aid = database.save_analysis(_analysis_result())
        database.mark_job_completed(old_job, aid)
        database.mark_job_completed(recent_job, aid)
        with database._conn() as connection:
            connection.execute(
                "UPDATE analysis_job SET finished_at = '2000-01-01T00:00:00' WHERE id = ?",
                (old_job,),
            )

        self.assertEqual(database.prune_finished_jobs(7), 1)
        self.assertIsNone(database.get_job(old_job))
        self.assertIsNotNone(database.get_job(recent_job))
        self.assertIsNotNone(database.get_analysis(aid))


if __name__ == "__main__":
    unittest.main()
