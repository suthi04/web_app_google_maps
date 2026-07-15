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
        issue = audience_insights.build_critical_issues(
            keywords, service_summary
        )[0]
        self.assertEqual(issue["severity"], "watch")


if __name__ == "__main__":
    unittest.main()
