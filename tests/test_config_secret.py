"""SECRET_KEY falls back to a random per-process key but must warn (multi-worker risk)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


class TestSecretKey(unittest.TestCase):
    def test_env_key_used_as_is_no_warning(self):
        key, used_random = config.resolve_secret_key("my-fixed-key")
        self.assertEqual(key, "my-fixed-key")
        self.assertFalse(used_random)

    def test_blank_env_generates_random_and_flags_warning(self):
        key, used_random = config.resolve_secret_key("")
        self.assertTrue(used_random)
        self.assertGreaterEqual(len(key), 32)
