"""GEMINI_MODEL มีค่า default + get_gemini_api_key() อ่านสดจาก env (patch ได้)"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


class TestGeminiConfig(unittest.TestCase):
    def test_default_model(self):
        self.assertEqual(config.GEMINI_MODEL, "gemini-2.5-flash-lite")

    def test_key_read_live_from_env(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-123"}, clear=False):
            self.assertEqual(config.get_gemini_api_key(), "test-key-123")

    def test_key_empty_when_unset(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False):
            self.assertEqual(config.get_gemini_api_key(), "")


if __name__ == "__main__":
    unittest.main()
