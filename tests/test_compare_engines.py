import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import compare_engines


class TestCompareEngines(unittest.TestCase):
    def test_rule_only_comparison_runs_headless(self):
        reviews = [
            {"text": "อาหารอร่อยมาก แต่บริการช้า"},
            {"text": "พนักงานน่ารัก รอนาน"},
        ]
        report = compare_engines.compare(reviews, run_llm=False)
        self.assertIn("rule", report)
        self.assertIn("llm", report)
        self.assertIsNone(report["llm"])              # skipped without key
        self.assertGreaterEqual(report["rule"]["total_phrases"], 1)
        self.assertIn("food", report["rule"]["per_aspect"])
