"""
tests/test_clause_pipeline.py
=============================
ทดสอบการทำงานระดับอนุประโยค (Phase 2):
- sentiment.analyze_all ตั้งอารมณ์ทั้งระดับรีวิว และระดับอนุประโยค
- aspect.tag_aspects ตั้ง aspects ให้แต่ละอนุประโยค + รวมเป็นของรีวิว
- aspect.aspect_sentiment_summary นับอารมณ์ "ตามอนุประโยค" (ไม่ broadcast ทั้งรีวิว)
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from core import aspect, sentiment


def _review_food_pos_service_neg():
    """รีวิวจำลอง: อนุประโยคแรกชมอาหาร (บวก), อนุประโยคสองบ่นบริการ (ลบ)"""
    return {
        "clean": "อาหารอร่อย บริการช้า",
        "tokens": ["อาหาร", "อร่อย", "บริการ", "ช้า"],
        "tokens_base": ["อาหาร", "อร่อย", "บริการ", "ช้า"],
        "clauses": [
            {"clean": "อาหารอร่อย", "tokens": ["อาหาร", "อร่อย"],
             "tokens_base": ["อาหาร", "อร่อย"]},
            {"clean": "บริการช้า", "tokens": ["บริการ", "ช้า"],
             "tokens_base": ["บริการ", "ช้า"]},
        ],
    }


class _LexiconEngineMixin:
    """บังคับใช้ engine แบบ lexicon ให้เทสต์เร็ว+คงที่ ไม่ขึ้นกับ .env (USE_MODEL)"""

    def setUp(self):
        patcher = mock.patch.object(config, "get_use_model", return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)


class TestClauseSentiment(_LexiconEngineMixin, unittest.TestCase):
    def test_analyze_all_sets_clause_sentiment(self):
        reviews = sentiment.analyze_all([_review_food_pos_service_neg()])
        clauses = reviews[0]["clauses"]
        self.assertEqual(clauses[0]["sentiment"], "positive")
        self.assertEqual(clauses[1]["sentiment"], "negative")

    def test_analyze_all_still_sets_review_sentiment(self):
        reviews = sentiment.analyze_all([_review_food_pos_service_neg()])
        self.assertIn(reviews[0]["sentiment"], {"positive", "neutral", "negative"})


class TestClauseAspectTagging(_LexiconEngineMixin, unittest.TestCase):
    def test_tag_aspects_per_clause_and_union(self):
        reviews = aspect.tag_aspects([_review_food_pos_service_neg()])
        clauses = reviews[0]["clauses"]
        self.assertEqual(clauses[0]["aspects"], ["food"])
        self.assertEqual(clauses[1]["aspects"], ["service"])
        self.assertEqual(set(reviews[0]["aspects"]), {"food", "service"})


class TestAspectLevelSummary(_LexiconEngineMixin, unittest.TestCase):
    def test_summary_counts_per_clause_not_broadcast(self):
        reviews = sentiment.analyze_all([_review_food_pos_service_neg()])
        reviews = aspect.tag_aspects(reviews)
        summary = aspect.aspect_sentiment_summary(reviews)
        # อาหาร: บวก 1 ; บริการ: ลบ 1 ; ไม่มีการ broadcast บวกไปบริการ
        self.assertEqual(summary["food"]["positive"], 1)
        self.assertEqual(summary["food"]["negative"], 0)
        self.assertEqual(summary["service"]["negative"], 1)
        self.assertEqual(summary["service"]["positive"], 0)

    def test_mention_only_aspect_not_marked_positive(self):
        # อนุประโยคชมอาหาร (บวก) + อนุประโยคกล่าวถึงบริการแบบกลาง
        review = {
            "clean": "อาหารอร่อยมาก มีที่จอดรถ",
            "tokens": ["อาหาร", "อร่อย", "มาก", "ที่จอดรถ"],
            "tokens_base": ["อาหาร", "อร่อย", "มาก", "ที่จอดรถ"],
            "clauses": [
                {"clean": "อาหารอร่อยมาก", "tokens": ["อาหาร", "อร่อย", "มาก"],
                 "tokens_base": ["อาหาร", "อร่อย", "มาก"]},
                {"clean": "มีที่จอดรถ", "tokens": ["ที่จอดรถ"],
                 "tokens_base": ["ที่จอดรถ"]},
            ],
        }
        reviews = aspect.tag_aspects(sentiment.analyze_all([review]))
        summary = aspect.aspect_sentiment_summary(reviews)
        # บรรยากาศ (ที่จอดรถ) ต้องไม่ถูกนับเป็นบวกจากการชมอาหาร
        self.assertEqual(summary["ambience"]["positive"], 0)
        self.assertEqual(summary["ambience"]["neutral"], 1)


if __name__ == "__main__":
    unittest.main()
