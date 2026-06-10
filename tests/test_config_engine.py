import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


class TestExtractEngine(unittest.TestCase):
    def test_default_is_rule(self):
        self.assertEqual(config.get_settings()["extract_engine"], "rule")

    def test_get_extract_engine_helper(self):
        self.assertIn(config.get_extract_engine(), {"rule", "llm"})
