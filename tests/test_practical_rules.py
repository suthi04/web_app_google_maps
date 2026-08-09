import unittest

from core import audience_insights, practical_rules


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

    def test_negated_cues_are_not_double_counted(self):
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

    def test_enrich_result_uses_phrase_evidence_and_adds_meta(self):
        result = {
            "reviews": [{"text": "รีวิวเดิมไม่มีข้อความเต็ม", "sentiment": "negative"}],
            "keywords": {
                "service": {
                    "negative": [{
                        "word": "รอคิวนาน",
                        "evidence_review_ids": ["R001"],
                    }]
                }
            },
        }
        practical_rules.enrich_result(result)
        self.assertEqual(result["reviews"][0]["review_id"], "R001")
        self.assertEqual(result["practical_insights"][0]["topic"], "queue")
        self.assertEqual(result["practical_insights_meta"]["evidence_review_count"], 1)


class TestSharedRuleOutputs(unittest.TestCase):
    def test_one_rule_set_feeds_consumer_cautions_and_operator_issues(self):
        result = {
            "reviews": [
                {"text": "รอคิวนานมาก", "sentiment": "negative"},
                {"text": "อาหารมาช้าในช่วงเย็น", "sentiment": "negative"},
            ],
            "keywords": {},
            "aspect_summary": {
                "service": {"positive": 0, "neutral": 0, "negative": 2, "total": 2},
            },
            "distribution": {
                "counts": {"positive": 0, "neutral": 0, "negative": 2},
                "pct": {"positive": 0, "neutral": 0, "negative": 100},
            },
        }
        audience_insights.enrich_result(result)

        before_you_go = result["consumer_summary"]["things_to_know"][0]
        caution = result["consumer_summary"]["cautions"][0]
        operator_issue = result["critical_issues"][0]
        self.assertEqual(before_you_go["topic"], "queue")
        self.assertEqual(caution["topic"], "queue")
        self.assertEqual(operator_issue["topic"], "queue")
        self.assertEqual(caution["source"], "practical_rules")
        self.assertIn("ช่วงพีค", operator_issue["strategy"])
        self.assertIn(before_you_go["advice"], result["consumer_summary"]["lazy_summary"]["detail"])

    def test_matching_rule_prevents_duplicate_phrase_caution(self):
        result = {
            "reviews": [{"text": "รอนานมาก", "sentiment": "negative"}],
            "keywords": {
                "service": {
                    "negative": [{
                        "word": "รอนาน",
                        "count": 2,
                        "review_count": 1,
                        "evidence_review_ids": ["R001"],
                    }]
                }
            },
            "aspect_summary": {
                "service": {"positive": 0, "neutral": 0, "negative": 1, "total": 1},
            },
            "distribution": {"pct": {"positive": 0, "neutral": 0, "negative": 100}},
        }
        audience_insights.enrich_result(result)
        queue_items = [
            item for item in result["consumer_summary"]["cautions"]
            if item.get("topic") == "queue" or "รอ" in item["text"]
        ]
        self.assertEqual(len(queue_items), 1)


if __name__ == "__main__":
    unittest.main()
