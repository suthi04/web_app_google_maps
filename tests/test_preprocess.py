"""
tests/test_preprocess.py
========================
ทดสอบว่า preprocess_review คืนทั้ง tokens (รวม negation แล้ว) และ tokens_base
(ก่อนรวม negation, ใช้สำหรับจับ aspect) และแนบ clauses ให้ filter_and_prepare
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import preprocess


class TestPreprocessNegation(unittest.TestCase):
    def test_returns_tokens_and_base(self):
        pp = preprocess.preprocess_review("อาหารไม่อร่อยเลย")
        self.assertIn("tokens", pp)
        self.assertIn("tokens_base", pp)
        self.assertIn("clean", pp)

    def test_tokens_have_merged_negation(self):
        pp = preprocess.preprocess_review("อาหารไม่อร่อยเลย")
        # tokens (สำหรับ sentiment/keyword) ต้องมี "ไม่อร่อย" เป็นหน่วยเดียว
        self.assertIn("ไม่อร่อย", pp["tokens"])
        # และต้องไม่มี "อร่อย" ลอย ๆ (กันนับเป็นบวก)
        self.assertNotIn("อร่อย", pp["tokens"])

    def test_tokens_base_keeps_unmerged_for_aspect(self):
        pp = preprocess.preprocess_review("อาหารไม่อร่อยเลย")
        # tokens_base (สำหรับจับ aspect) ยังมี "อร่อย" เพื่อ map เข้าหมวดอาหาร
        self.assertIn("อร่อย", pp["tokens_base"])


class TestFilterAndPrepareClauses(unittest.TestCase):
    def test_attaches_clauses(self):
        raw = [{"text": "อาหารอร่อยมาก รสชาติดี ประทับใจ",
                "rating": 5, "review_date": "2026-01-01"}]
        out = preprocess.filter_and_prepare(raw)
        self.assertEqual(len(out), 1)
        self.assertIn("clauses", out[0])
        self.assertGreaterEqual(len(out[0]["clauses"]), 1)
        self.assertIn("tokens", out[0]["clauses"][0])
        self.assertIn("tokens_base", out[0]["clauses"][0])

    def test_splits_contrastive_review_into_two_clauses(self):
        raw = [{"text": "อาหารอร่อย แต่บริการช้า", "rating": 3, "review_date": None}]
        out = preprocess.filter_and_prepare(raw)
        self.assertEqual(len(out[0]["clauses"]), 2)


class TestRawTokensAndClauseSplit(unittest.TestCase):
    def test_clause_has_raw_tokens(self):
        from core import preprocess
        out = preprocess.filter_and_prepare(
            [{"text": "อาหารอร่อยมาก แต่ บริการช้า", "rating": 5, "review_date": None}]
        )
        self.assertEqual(len(out), 1)
        clauses = out[0]["clauses"]
        self.assertGreaterEqual(len(clauses), 2)
        for c in clauses:
            self.assertIn("raw_tokens", c)
            self.assertTrue(all(isinstance(t, str) for t in c["raw_tokens"]))

    def test_raw_tokens_keep_function_words(self):
        from core import preprocess
        out = preprocess.preprocess_review("ราคาไม่แพง")
        self.assertIn("raw_tokens", out)
        # negation word retained in raw_tokens (not stopword-stripped)
        self.assertIn("ไม่", out["raw_tokens"])


if __name__ == "__main__":
    unittest.main()
