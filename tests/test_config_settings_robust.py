import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


class TestRobustSettings(unittest.TestCase):
    def setUp(self):
        config._settings_cache.update({"path": None, "mtime": None, "data": {}})

    def tearDown(self):
        config._settings_cache.update({"path": None, "mtime": None, "data": {}})

    def test_malformed_values_fall_back_instead_of_crashing(self):
        with mock.patch.object(
            config,
            "_load_overrides",
            return_value={
                "max_reviews": "not-a-number",
                "use_model": "false",
                "extract_engine": "unknown",
            },
        ):
            settings = config.get_settings()
        self.assertEqual(settings["max_reviews"], config._DEFAULTS["max_reviews"])
        self.assertFalse(settings["use_model"])
        self.assertEqual(settings["extract_engine"], "rule")

    def test_bounded_env_integer_handles_invalid_and_out_of_range_values(self):
        with mock.patch.dict(os.environ, {"TEST_NUMBER": "broken"}):
            self.assertEqual(config._env_int("TEST_NUMBER", 25, 10, 100), 25)
        with mock.patch.dict(os.environ, {"TEST_NUMBER": "999"}):
            self.assertEqual(config._env_int("TEST_NUMBER", 25, 10, 100), 100)
        with mock.patch.dict(os.environ, {"TEST_NUMBER": "-5"}):
            self.assertEqual(config._env_int("TEST_NUMBER", 25, 10, 100), 10)

    def test_invalid_json_and_non_object_json_are_treated_as_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "settings.json")
            for content in ("{broken", "[]"):
                with self.subTest(content=content):
                    with open(path, "w", encoding="utf-8") as file:
                        file.write(content)
                    config._settings_cache.update(
                        {"path": None, "mtime": None, "data": {}}
                    )
                    with mock.patch.object(config, "SETTINGS_PATH", path):
                        self.assertEqual(config._load_overrides(), {})

if __name__ == "__main__":
    unittest.main()
