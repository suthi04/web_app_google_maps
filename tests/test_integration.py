"""
tests/test_integration.py
=========================
สโม้คเทสต์ end-to-end ของ pipeline บนข้อมูลตัวอย่าง (โหมด demo + lexicon)
บังคับโหมด demo/lexicon เพื่อให้เร็ว คงที่ และไม่ขึ้นกับ .env (APIFY/USE_MODEL)

จุดประสงค์: กันการ regress ของการต่อท่อทั้งระบบหลังแก้ Phase 1–2
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from core import pipeline


class TestPipelineSmoke(unittest.TestCase):
    def setUp(self):
        for name, val in (("get_apify_token", ""), ("get_use_model", False)):
            p = mock.patch.object(config, name, return_value=val)
            p.start()
            self.addCleanup(p.stop)
        self.result = pipeline.run_analysis("")

    def test_runs_and_has_reviews(self):
        self.assertGreater(self.result["total_reviews"], 0)
        self.assertEqual(self.result["engine"], "lexicon (พจนานุกรมคำ)")

    def test_distribution_percentages_sum_to_100(self):
        pct = self.result["distribution"]["pct"]
        self.assertEqual(pct["positive"] + pct["neutral"] + pct["negative"], 100)

    def test_aspect_summary_has_three_aspects(self):
        self.assertEqual(
            set(self.result["aspect_summary"].keys()),
            {"food", "service", "ambience"},
        )

    def test_negation_keyword_flows_to_output(self):
        # หลังแก้ Phase 1 คำปฏิเสธควรโผล่เป็นคำสำคัญ (เช่น "ไม่ดี", "ไม่แนะนำ")
        all_words = []
        for asp in self.result["keywords"].values():
            for bucket in asp.values():
                all_words += [k["word"] for k in bucket]
        self.assertTrue(
            any(w.startswith("ไม่") for w in all_words),
            "expected at least one negation-merged keyword in output",
        )

    def test_insights_present_for_each_aspect(self):
        aspects = {i["aspect"] for i in self.result["insights"]}
        self.assertTrue({"food", "service", "ambience"}.issubset(aspects))

    def test_keywords_are_phrases_not_bare_nouns(self):
        bad = {"อาหาร", "เมนู", "ร้าน", "ดี", "อร่อย", "ชอบ", "แนะนำ"}
        words = []
        for asp in self.result["keywords"].values():
            for bucket in asp.values():
                words += [k["word"] for k in bucket]
        self.assertTrue(words, "expected some phrases")
        self.assertEqual([w for w in words if w in bad], [])

    def test_keywords_contract_shape(self):
        kw = self.result["keywords"]
        self.assertEqual(set(kw), {"food", "service", "ambience"})
        for asp in kw.values():
            self.assertEqual(set(asp), {"positive", "neutral", "negative"})


if __name__ == "__main__":
    unittest.main()
