import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import audience_insights, insights


def _keywords():
    return {
        "food": {
            "positive": [{"word": "อาหารอร่อย", "count": 5, "review_count": 3,
                          "evidence_review_ids": ["R001", "R002", "R003"]}],
            "neutral": [],
            "negative": [{"word": "วัตถุดิบไม่สด", "count": 2, "review_count": 2,
                          "evidence_review_ids": ["R004", "R005"]}],
        },
        "service": {
            "positive": [{"word": "บริการดี", "count": 4, "review_count": 3,
                          "evidence_review_ids": ["R001", "R006", "R007"]}],
            "neutral": [],
            "negative": [{"word": "รอนาน", "count": 3, "review_count": 2,
                          "evidence_review_ids": ["R008", "R009"]}],
        },
        "ambience": {
            "positive": [{"word": "บรรยากาศดี", "count": 3, "review_count": 3,
                          "evidence_review_ids": ["R001", "R002", "R010"]}],
            "neutral": [{"word": "มีที่จอดรถ", "count": 2, "review_count": 2,
                         "evidence_review_ids": ["R003", "R004"]}],
            "negative": [],
        },
    }


def _aspect_summary():
    return {
        "food": {"positive": 8, "neutral": 0, "negative": 2, "total": 10},
        "service": {"positive": 5, "neutral": 1, "negative": 4, "total": 10},
        "ambience": {"positive": 8, "neutral": 2, "negative": 0, "total": 10},
    }


class TestConsumerSummary(unittest.TestCase):
    def test_consumer_sections_and_critical_strategy_are_evidence_led(self):
        result = audience_insights.build_consumer_summary(
            _keywords(),
            {"pct": {"positive": 70, "neutral": 10, "negative": 20}},
            _aspect_summary(),
        )
        self.assertTrue(result["things_to_know"])
        self.assertTrue(result["cautions"])
        self.assertIn("70%", result["lazy_summary"]["detail"])

        issues = audience_insights.build_critical_issues(
            _keywords(), _aspect_summary()
        )
        waiting = next(issue for issue in issues if issue["text"] == "รอนาน")
        self.assertEqual(waiting["severity"], "critical")
        self.assertEqual(waiting["review_count"], 2)
        self.assertEqual(waiting["evidence_review_ids"], ["R008", "R009"])
        self.assertIn("ช่วงพีค", waiting["strategy"])

    def test_positive_phrase_in_legacy_negative_bucket_is_not_an_alert(self):
        keywords = _keywords()
        keywords["service"]["negative"].append(
            {"word": "ยิ้มแย้มดีมาก", "count": 1}
        )
        issues = audience_insights.build_critical_issues(
            keywords, _aspect_summary()
        )
        self.assertNotIn("ยิ้มแย้มดีมาก", {item["text"] for item in issues})

    def test_before_you_go_does_not_fall_back_to_generic_food_praise(self):
        keywords = {
            "food": {"positive": [{
                "word": "อาหารอร่อย", "count": 4,
                "review_count": 2,
                "evidence_review_ids": ["R001", "R002"],
            }], "neutral": [], "negative": []},
        }
        result = audience_insights.build_consumer_summary(
            keywords,
            {"pct": {"positive": 100, "neutral": 0, "negative": 0}},
            {},
            [
                {"review_id": "R001", "text": "อาหารอร่อยมาก", "sentiment": "positive"},
                {"review_id": "R002", "text": "รสชาติดี อาหารอร่อย", "sentiment": "positive"},
            ],
        )
        self.assertEqual(result["things_to_know"], [])

    def test_before_you_go_groups_synonyms_and_unique_review_evidence(self):
        reviews = [
            {"review_id": "R001", "text": "รอคิวนานมาก", "sentiment": "negative"},
            {"review_id": "R002", "text": "อาหารมาช้า ต้องเผื่อเวลา", "sentiment": "negative"},
            {"review_id": "R003", "text": "บริการช้าและรอนาน", "sentiment": "negative"},
        ]
        result = audience_insights.build_consumer_summary(
            {}, {"pct": {}}, {}, reviews,
        )
        queue = next(item for item in result["things_to_know"] if item["topic"] == "queue")
        self.assertEqual(queue["status"], "negative")
        self.assertEqual(queue["review_count"], 3)
        self.assertEqual(queue["evidence_review_ids"], ["R001", "R002", "R003"])
        self.assertEqual(queue["evidence_label"], "พูดถึงหลายครั้ง")

    def test_before_you_go_keeps_contradictory_parking_reviews_visible(self):
        reviews = [
            {"review_id": "R001", "text": "มีที่จอดรถ จอดสะดวกมาก", "sentiment": "positive"},
            {"review_id": "R002", "text": "ที่จอดรถน้อย หาที่จอดยาก", "sentiment": "negative"},
        ]
        result = audience_insights.build_consumer_summary(
            {}, {"pct": {}}, {}, reviews,
        )
        parking = next(item for item in result["things_to_know"] if item["topic"] == "parking")
        self.assertEqual(parking["status"], "mixed")
        self.assertEqual(parking["positive_review_count"], 1)
        self.assertEqual(parking["negative_review_count"], 1)
        self.assertIn("ไม่ตรงกัน", parking["title"])

    def test_before_you_go_marks_single_mention_as_preliminary(self):
        result = audience_insights.build_consumer_summary(
            {}, {"pct": {}}, {},
            [{"review_id": "R001", "text": "รับเฉพาะเงินสด", "sentiment": "negative"}],
        )
        payment = next(item for item in result["things_to_know"] if item["topic"] == "payment")
        self.assertEqual(payment["evidence_level"], "preliminary")
        self.assertEqual(payment["evidence_label"], "พูดถึง 1 ครั้ง")
        self.assertEqual(payment["status"], "negative")

    def test_before_you_go_only_shows_time_context_found_in_source_review(self):
        reviews = [
            {"review_id": "R001", "text": "ช่วงเย็นคนเยอะและเสียงดัง", "sentiment": "negative"},
            {"review_id": "R002", "text": "วันหยุดคนแน่นมาก", "sentiment": "negative"},
        ]
        result = audience_insights.build_consumer_summary(
            {}, {"pct": {}}, {}, reviews,
        )
        crowd = next(item for item in result["things_to_know"] if item["topic"] == "crowd_noise")
        self.assertEqual(crowd["context_labels"], ["ช่วงเย็น", "วันหยุด"])
        self.assertEqual(crowd["context_text"], "มีผู้พูดถึงในช่วงเย็นและวันหยุด")
        self.assertNotIn("ช่วงเที่ยง", crowd["context_labels"])

    def test_before_you_go_exposes_action_status_and_rank(self):
        reviews = [
            {"review_id": "R001", "text": "รอคิวนานมาก", "sentiment": "negative"},
            {"review_id": "R002", "text": "มีเดลิเวอรี ส่งอาหารได้", "sentiment": "positive"},
            {"review_id": "R003", "text": "สั่งกลับบ้านได้ มีเดลิเวอรี", "sentiment": "positive"},
        ]
        items = audience_insights.build_consumer_summary(
            {}, {"pct": {}}, {}, reviews,
        )["things_to_know"]
        queue = next(item for item in items if item["topic"] == "queue")
        takeaway = next(item for item in items if item["topic"] == "takeaway")
        self.assertLess(queue["rank"], takeaway["rank"])
        self.assertEqual(queue["action_tier"], "plan")
        self.assertEqual(queue["status_label"], "ควรวางแผน")
        self.assertEqual(takeaway["action_tier"], "ready")
        self.assertEqual(takeaway["status_label"], "ข้อมูลที่เป็นประโยชน์")

    def test_before_you_go_meta_counts_unique_evidence_reviews(self):
        reviews = [
            {"review_id": "R001", "text": "รอนานและรับเฉพาะเงินสด", "sentiment": "negative"},
            {"review_id": "R002", "text": "อาหารมาช้า", "sentiment": "negative"},
        ]
        result = audience_insights.build_consumer_summary(
            {}, {"pct": {}}, {}, reviews,
        )
        meta = result["things_to_know_meta"]
        self.assertEqual(meta["topic_count"], 2)
        self.assertEqual(meta["evidence_review_count"], 2)
        self.assertEqual(meta["attention_count"], 2)
        self.assertEqual(meta["repeated_count"], 1)

    def test_negated_positive_cue_is_not_double_counted(self):
        reviews = [
            {"review_id": "R001", "text": "ราคาไม่แพงและคุ้มค่า", "sentiment": "positive"},
            {"review_id": "R002", "text": "ร้านไม่สะอาด ห้องน้ำโทรม", "sentiment": "negative"},
        ]
        result = audience_insights.build_consumer_summary(
            {}, {"pct": {}}, {}, reviews,
        )
        price = next(item for item in result["things_to_know"] if item["topic"] == "price")
        cleanliness = next(item for item in result["things_to_know"] if item["topic"] == "cleanliness")
        self.assertEqual(price["status"], "positive")
        self.assertEqual(cleanliness["status"], "negative")

    def test_lazy_summary_uses_only_repeated_complete_strengths(self):
        keywords = {
            "food": {
                "positive": [{
                    "word": "2 อย่างแรกมาถายใน 10 นาที",
                    "count": 1,
                    "review_count": 1,
                    "evidence_review_ids": ["R001"],
                }],
                "neutral": [],
                "negative": [],
            },
            "ambience": {
                "positive": [{
                    "word": "บรรยากาศดี",
                    "count": 3,
                    "review_count": 2,
                    "evidence_review_ids": ["R002", "R003"],
                }],
                "neutral": [],
                "negative": [],
            },
        }
        result = audience_insights.build_consumer_summary(
            keywords,
            {"pct": {"positive": 70, "neutral": 20, "negative": 10}},
            {},
        )
        summary = result["lazy_summary"]
        self.assertIn("คำชมซ้ำ", summary["detail"])
        self.assertIn("บรรยากาศดี", summary["detail"])
        self.assertNotIn("2 อย่างแรก", summary["detail"])
        self.assertEqual(summary["evidence_review_ids"], ["R002", "R003"])

    def test_review_level_hygiene_risk_is_not_lost_when_phrase_is_missing(self):
        reviews = [{
            "review_id": "R001",
            "text": "แมลงวันตอมเยอะมากๆ แต่ไก่ทอดอร่อย",
            "sentiment": "negative",
        }]
        result = audience_insights.build_consumer_summary(
            {}, {"pct": {"positive": 0, "neutral": 0, "negative": 100}}, {}, reviews,
        )
        risk = next(
            item for item in result["cautions"]
            if item.get("risk_key") == "pests"
        )
        self.assertEqual(risk["review_count"], 1)
        self.assertEqual(risk["severity"], "watch")
        self.assertEqual(risk["evidence_review_ids"], ["R001"])
        self.assertIn("แมลง", risk["text"])

    def test_single_review_watch_strategy_is_explicitly_caveated(self):
        reviews = [{
            "review_id": "R001",
            "text": "อาหารบูดและมีกลิ่นผิดปกติ",
            "sentiment": "negative",
        }]
        issue = audience_insights.build_critical_issues(
            {}, {}, reviews=reviews,
        )[0]
        self.assertEqual(issue["severity"], "watch")
        self.assertIn("ตรวจสอบว่าพบซ้ำ", issue["strategy"])

    def test_enrich_marks_rating_and_text_sentiment_disagreement(self):
        result = {
            "reviews": [{
                "text": "น้ำซุปจืด เนื้อเหนียว แต่โดยรวมโอเค",
                "rating": 5,
                "sentiment": "negative",
            }],
            "keywords": {},
            "distribution": {"pct": {}},
            "aspect_summary": {},
        }
        audience_insights.enrich_result(result)
        review = result["reviews"][0]
        self.assertEqual(review["rating_sentiment"], "positive")
        self.assertTrue(review["rating_sentiment_mismatch"])
        self.assertEqual(result["rating_sentiment_mismatch_count"], 1)


class TestRichActionableInsights(unittest.TestCase):
    def test_strength_explains_evidence_and_next_strategy(self):
        result = insights.generate_insights(_aspect_summary(), _keywords())
        food = next(item for item in result if item["aspect"] == "food")
        self.assertEqual(food["level"], "strength")
        self.assertIn("อาหารอร่อย", food["reason"])
        self.assertTrue(food["evidence"])
        self.assertIn("มาตรฐาน", food["strategy"])

    def test_single_review_issue_stays_preliminary_even_when_aspect_is_negative(self):
        keywords = _keywords()
        keywords["service"]["negative"] = [{
            "word": "ไม่ใส่ใจ", "count": 3, "review_count": 1,
            "evidence_review_ids": ["R008"],
        }]
        service_summary = _aspect_summary()
        service_summary["service"] = {
            "positive": 1, "neutral": 0, "negative": 9, "total": 10,
        }
        issue = next(
            item for item in audience_insights.build_critical_issues(
                keywords, service_summary
            )
            if item["text"] == "ไม่ใส่ใจ"
        )
        self.assertEqual(issue["severity"], "watch")


if __name__ == "__main__":
    unittest.main()
