import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


class TestExtractEngine(unittest.TestCase):
    def test_default_is_rule(self):
        # ต้องแยกตัวจาก data/settings.json ของเครื่อง dev (ผู้ใช้อาจตั้ง llm ไว้) —
        # ทดสอบ "ค่าเริ่มต้น" จริง ๆ เมื่อไม่มี override
        with mock.patch.object(config, "_load_overrides", return_value={}):
            self.assertEqual(config.get_settings()["extract_engine"], "rule")

    def test_get_extract_engine_helper(self):
        self.assertIn(config.get_extract_engine(), {"rule", "llm"})
