import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


class TestSaveSettingsEngine(unittest.TestCase):
    def test_extract_engine_is_persisted(self):
        captured = {}
        with mock.patch.object(config, "save_settings",
                               side_effect=lambda c: captured.update(c)):
            import app
            client = app.app.test_client()
            client.post("/settings", data={"engine": "lexicon",
                                           "extract_engine": "llm",
                                           "max_reviews": "20"})
        self.assertEqual(captured.get("extract_engine"), "llm")
