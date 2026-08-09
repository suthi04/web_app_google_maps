import unittest
from unittest import mock

from core import practical_rules
import app as webapp


class TestPracticalRules(unittest.TestCase):
    def test_generic_food_praise_is_not_before_you_go_information(self):
        items = practical_rules.build_practical_insights([
            {"review_id": "R001", "text": "อาหารอร่อยมาก", "sentiment": "positive"},
            {"review_id": "R002", "text": "รสชาติดี อาหารอร่อย", "sentiment": "positive"},
        ])
        self.assertEqual(items, [])

    def test_groups_queue_synonyms_by_unique_review(self):
        items = practical_rules.build_practical_insights([
            {"review_id": "R001", "text": "รอคิวนานมาก", "sentiment": "negative"},
            {"review_id": "R002", "text": "อาหารมาช้า ต้องเผื่อเวลา", "sentiment": "negative"},
            {"review_id": "R003", "text": "บริการช้าและรอนาน", "sentiment": "negative"},
        ])
        queue = next(item for item in items if item["topic"] == "queue")
        self.assertEqual(queue["status"], "negative")
        self.assertEqual(queue["review_count"], 3)
        self.assertEqual(queue["evidence_review_ids"], ["R001", "R002", "R003"])

    def test_contradictory_parking_reviews_remain_visible(self):
        items = practical_rules.build_practical_insights([
            {"review_id": "R001", "text": "มีที่จอดรถ จอดสะดวกมาก", "sentiment": "positive"},
            {"review_id": "R002", "text": "ที่จอดรถน้อย หาที่จอดยาก", "sentiment": "negative"},
        ])
        parking = next(item for item in items if item["topic"] == "parking")
        self.assertEqual(parking["status"], "mixed")
        self.assertEqual(parking["positive_review_count"], 1)
        self.assertEqual(parking["negative_review_count"], 1)

    def test_negated_positive_cue_is_not_double_counted(self):
        items = practical_rules.build_practical_insights([
            {"review_id": "R001", "text": "ราคาไม่แพงและคุ้มค่า", "sentiment": "positive"},
            {"review_id": "R002", "text": "ร้านไม่สะอาด ห้องน้ำโทรม", "sentiment": "negative"},
        ])
        price = next(item for item in items if item["topic"] == "price")
        cleanliness = next(item for item in items if item["topic"] == "cleanliness")
        self.assertEqual(price["status"], "positive")
        self.assertEqual(cleanliness["status"], "negative")

    def test_context_only_comes_from_source_reviews(self):
        items = practical_rules.build_practical_insights([
            {"review_id": "R001", "text": "ช่วงเย็นคนเยอะและเสียงดัง", "sentiment": "negative"},
            {"review_id": "R002", "text": "วันหยุดคนแน่นมาก", "sentiment": "negative"},
        ])
        crowd = next(item for item in items if item["topic"] == "crowd_noise")
        self.assertEqual(crowd["context_labels"], ["ช่วงเย็น", "วันหยุด"])

    def test_enrich_result_adds_stable_evidence_and_meta(self):
        result = {"reviews": [
            {"text": "รอนานและรับเฉพาะเงินสด", "sentiment": "negative"},
            {"text": "อาหารมาช้า", "sentiment": "negative"},
        ]}
        practical_rules.enrich_result(result)
        self.assertEqual(
            [review["review_id"] for review in result["reviews"]],
            ["R001", "R002"],
        )
        self.assertEqual(result["practical_insights_meta"]["topic_count"], 2)
        self.assertEqual(result["practical_insights_meta"]["evidence_review_count"], 2)
        self.assertEqual(result["practical_insights_meta"]["attention_count"], 2)

    def test_dashboard_renders_rule_cards_with_evidence_ids(self):
        payload = {
            "id": 1,
            "store_name": "ร้านทดสอบ",
            "source_url": "",
            "total_reviews": 2,
            "fetched_reviews": 2,
            "engine": "lexicon",
            "extract_engine": "rule",
            "narrative": {"engine": "rule", "consumer": {}, "entrepreneur": {}},
            "distribution": {
                "counts": {"positive": 0, "neutral": 0, "negative": 2},
                "pct": {"positive": 0, "neutral": 0, "negative": 100},
                "total": 2,
            },
            "aspect_summary": {},
            "keywords": {},
            "insights": [],
            "reviews": [
                {"text": "รอคิวนานมาก", "rating": 2, "review_date": "", "sentiment": "negative", "aspects": []},
                {"text": "อาหารมาช้า", "rating": 2, "review_date": "", "sentiment": "negative", "aspects": []},
            ],
            "is_saved": False,
            "created_at": "2026-08-09 12:00:00",
        }
        with mock.patch.object(webapp.database, "get_analysis", return_value=payload):
            response = webapp.app.test_client().get("/dashboard/1")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("เรื่องที่ควรรู้ก่อนไป", html)
        self.assertIn("อาจต้องรอคิว", html)
        self.assertIn("R001, R002", html)


if __name__ == "__main__":
    unittest.main()
