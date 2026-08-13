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

    def test_operator_plan_ranks_evidence_without_calendar_claims(self):
        actionable = insights.generate_insights(_aspect_summary(), _keywords())
        issues = audience_insights.build_critical_issues(
            _keywords(), _aspect_summary()
        )
        plan = audience_insights.build_operator_plan(actionable, issues)

        self.assertEqual(len(plan["items"]), 3)
        service = next(item for item in plan["items"] if item["aspect"] == "service")
        self.assertEqual(service["rank"], 1)
        self.assertEqual(service["priority"], "improve")
        self.assertEqual(service["priority_label"], "ควรปรับปรุง")
        self.assertEqual(service["evidence_count"], 2)
        self.assertIn("รอบถัดไป", service["measure"])
        self.assertNotIn("วันนี้", service["measure"])
        food = next(item for item in plan["items"] if item["aspect"] == "food")
        self.assertEqual(food["headline"], "อาหารอร่อย")
        self.assertNotIn("วัตถุดิบไม่สด", food["headline"])

    def test_operator_plan_requires_three_reviews_for_top_priority(self):
        keywords = _keywords()
        service_issue = keywords["service"]["negative"][0]
        service_issue["review_count"] = 3
        service_issue["evidence_review_ids"] = ["R008", "R009", "R011"]
        actionable = insights.generate_insights(_aspect_summary(), keywords)
        issues = audience_insights.build_critical_issues(
            keywords, _aspect_summary()
        )
        plan = audience_insights.build_operator_plan(actionable, issues)

        service = next(item for item in plan["items"] if item["aspect"] == "service")
        self.assertEqual(service["priority"], "first")
        self.assertEqual(service["priority_label"], "ควรจัดการก่อน")
        self.assertEqual(plan["counts"]["first"], 1)

    def test_operator_playbook_separates_risks_from_evidenced_strengths(self):
        issues = audience_insights.build_critical_issues(
            _keywords(), _aspect_summary()
        )
        playbook = audience_insights.build_operator_playbook(_keywords(), issues)

        waiting = next(item for item in playbook["risks"] if item["topic"] == "รอนาน")
        self.assertEqual(waiting["review_count"], 2)
        self.assertEqual(waiting["evidence_review_ids"], ["R008", "R009"])
        self.assertIn("ช่วงพีค", waiting["action"])

        self.assertEqual(playbook["opportunities"][0]["topic"], "อาหารอร่อย")
        self.assertEqual(playbook["opportunities"][0]["review_count"], 3)
        self.assertIn("มาตรฐาน", playbook["opportunities"][0]["action"])

    def test_operator_brief_reports_evidence_without_calendar_claims(self):
        actionable = insights.generate_insights(_aspect_summary(), _keywords())
        issues = audience_insights.build_critical_issues(
            _keywords(), _aspect_summary()
        )
        plan = audience_insights.build_operator_plan(
            actionable,
            issues,
            _keywords(),
            {"total": 10, "pct": {"positive": 70}},
            10,
        )

        self.assertIn("บริการ", plan["brief"]["headline"])
        self.assertEqual(plan["brief"]["positive_pct"], 70)
        self.assertGreater(plan["brief"]["evidence_count"], 0)
        self.assertEqual(plan["brief"]["total_reviews"], 10)
        self.assertNotIn("วันนี้", plan["brief"]["detail"])
        self.assertEqual(len(plan["next_checks"]), 3)

    def test_operator_strength_only_brief_uses_plain_customer_language(self):
        plan = audience_insights.build_operator_plan([{
            "aspect": "food",
            "aspect_th": "อาหาร",
            "level": "strength",
            "positive_pct": 80,
            "negative_pct": 5,
            "sample_size": 20,
            "evidence_review_ids": ["R001", "R002", "R003"],
            "evidence": [{"text": "อาหารอร่อย"}],
        }], [])

        self.assertEqual(plan["brief"]["headline"], "ลูกค้าชอบอาหารของร้าน")
        self.assertEqual(
            plan["brief"]["detail"],
            "รีวิวส่วนใหญ่พูดถึงอาหารในทางบวก ควรรักษาคุณภาพจุดนี้ให้ดีเหมือนเดิม",
        )
        self.assertNotIn("จุดจำที่ทำซ้ำได้", plan["brief"]["headline"])
        self.assertNotIn("ถอดเป็นมาตรฐาน", plan["brief"]["detail"])

    def test_gemini_overview_and_visit_tip_keep_review_evidence(self):
        narrative = {
            "overview": {
                "headline": "อาหารเด่น แต่ควรเผื่อเวลาช่วงคนเยอะ",
                "detail": "ลูกค้าชมรสชาติ ขณะเดียวกันมีเสียงเรื่องการรอคิว",
                "evidence_review_ids": ["R001", "R008"],
            },
            "visit_tips": [{
                "title": "ช่วงคนเยอะอาจรอนาน",
                "detail": "มีลูกค้าพูดถึงการรอคิว",
                "advice": "ควรเผื่อเวลาก่อนไป",
                "aspect": "service", "sentiment": "negative",
                "evidence_review_ids": ["R008"], "review_count": 1,
            }],
        }
        result = audience_insights.build_consumer_summary(
            _keywords(),
            {"pct": {"positive": 70, "neutral": 10, "negative": 20}},
            _aspect_summary(), narrative=narrative,
        )
        self.assertEqual(result["lazy_summary"]["source"], "gemini")
        self.assertEqual(result["lazy_summary"]["evidence_review_ids"], ["R001", "R008"])
        self.assertTrue(any(item.get("source") == "gemini" for item in result["things_to_know"]))


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

    def test_gemini_narrative_improves_reason_and_strategy_without_changing_level(self):
        narrative = {
            "aspect_summaries": [{
                "aspect": "food", "headline": "รสชาติเป็นจุดเด่น",
                "detail": "ลูกค้าชมรสชาติและความสดอย่างชัดเจน",
                "evidence_review_ids": ["R001", "R002"],
            }],
            "actions": [{
                "aspect": "food", "title": "รักษามาตรฐานเมนูเด่น",
                "reason": "ลูกค้าชมรสชาติ",
                "action": "บันทึกสูตรและตรวจรสชาติก่อนเสิร์ฟทุกวัน",
                "evidence_review_ids": ["R001"],
            }],
        }
        food = next(item for item in insights.generate_insights(
            _aspect_summary(), _keywords(), narrative=narrative
        ) if item["aspect"] == "food")
        self.assertEqual(food["level"], "strength")
        self.assertEqual(food["source"], "gemini")
        self.assertIn("ความสด", food["reason"])
        self.assertIn("ตรวจรสชาติ", food["strategy"])
        self.assertEqual(food["evidence_review_ids"], ["R001", "R002"])


if __name__ == "__main__":
    unittest.main()
