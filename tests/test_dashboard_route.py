"""หน้า dashboard ต้องแสดง engine ที่ "ทำงานจริง" (อารมณ์ + สกัดวลี) ตามที่
README สัญญา และต้องไม่ฝัง payload ซ้ำเป็น JSON ก้อนใหญ่ (dead code เดิม)"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app
from db import database


def _payload(extract_engine="rule"):
    pct = {"positive": 50, "neutral": 30, "negative": 20}
    counts = {"positive": 5, "neutral": 3, "negative": 2}
    p = {
        "id": 1, "is_saved": False,
        "store_name": "ครัวบ้านสวน", "source_url": "https://maps.google.com/?cid=1",
        "total_reviews": 10, "fetched_reviews": 12,
        "engine": "WangchanBERTa",
        "distribution": {"counts": counts, "total": 10, "pct": pct},
        "aspect_summary": {}, "keywords": {}, "insights": [],
        "reviews": [{"text": "อร่อย", "rating": 5, "review_date": None,
                     "sentiment": "positive", "aspects": ["food"]}],
    }
    if extract_engine is not None:
        p["extract_engine"] = extract_engine
    return p


def _get_dashboard(payload):
    with mock.patch.object(database, "get_analysis", return_value=payload):
        return app.app.test_client().get("/dashboard/1").get_data(as_text=True)


class TestDashboardEngineBadges(unittest.TestCase):
    def test_shows_sentiment_engine(self):
        html = _get_dashboard(_payload())
        self.assertIn("WangchanBERTa", html)

    def test_shows_rule_extract_engine(self):
        html = _get_dashboard(_payload(extract_engine="rule"))
        self.assertIn("Rule-based", html)

    def test_shows_llm_extract_engine(self):
        html = _get_dashboard(_payload(extract_engine="llm"))
        self.assertIn("Gemini", html)

    def test_old_payload_without_extract_engine_still_renders(self):
        html = _get_dashboard(_payload(extract_engine=None))
        self.assertIn("ครัวบ้านสวน", html)

    def test_gemini_fallback_shows_actual_engine_and_updates_picker(self):
        payload = _payload(extract_engine="rule")
        payload["extract_engine_requested"] = "llm"
        payload["extract_engine_fallback"] = True
        html = _get_dashboard(payload)
        self.assertIn('data-actual-extract-engine="rule"', html)
        self.assertIn('data-sync-result-engine="1"', html)
        self.assertIn('data-extract-fallback="1"', html)
        self.assertIn("Gemini ไม่พร้อม งานนี้จึงใช้ Rule-based", html)

    def test_successful_gemini_result_discloses_evidence_verified_summary(self):
        payload = _payload(extract_engine="llm")
        payload["extract_engine_requested"] = "llm"
        payload["analysis_narrative"] = {
            "overview": {
                "headline": "รสชาติเป็นจุดเด่นของร้าน",
                "detail": "ลูกค้าชมอาหารอย่างชัดเจน",
                "evidence_review_ids": ["R001"],
            },
            "visit_tips": [], "aspect_summaries": [], "actions": [],
        }
        html = _get_dashboard(payload)
        self.assertIn('data-actual-extract-engine="llm"', html)
        self.assertIn('data-sync-result-engine="1"', html)
        self.assertIn("สรุปด้วย Gemini · ตรวจหลักฐานแล้ว", html)
        self.assertIn("Gemini สรุปจากรีวิวที่อ้างอิงได้", html)
        self.assertIn("รสชาติเป็นจุดเด่นของร้าน", html)


class TestNoDeadJsonBlob(unittest.TestCase):
    def test_analysis_data_script_removed(self):
        html = _get_dashboard(_payload())
        self.assertNotIn('id="analysis-data"', html)


class TestAudienceDashboard(unittest.TestCase):
    def test_before_you_go_uses_ranked_rule_cards_with_traceable_evidence(self):
        payload = _payload()
        payload["reviews"] = [
            {"text": "ช่วงเย็นรอคิวนานมาก", "rating": 2, "review_date": None,
             "sentiment": "negative", "aspects": ["service"]},
            {"text": "อาหารมาช้า ต้องเผื่อเวลา", "rating": 2, "review_date": None,
             "sentiment": "negative", "aspects": ["service"]},
        ]
        html = _get_dashboard(payload)
        self.assertIn('class="know-item rule-topic-card', html)
        self.assertIn("คิวและเวลารอ", html)
        self.assertIn('class="rule-quick-advice"', html)
        self.assertNotIn('class="rule-topic-summary"', html)
        self.assertIn('data-evidence="R001,R002"', html)
        self.assertNotIn("Rule-based · ตรวจสอบได้", html)

    def test_renders_consumer_and_operator_persona_tabs(self):
        html = _get_dashboard(_payload())
        self.assertIn("สำหรับผู้บริโภค", html)
        self.assertIn("สำหรับผู้ประกอบการ", html)
        self.assertIn('class="persona-icon"', html)
        self.assertIn('class="persona-copy"', html)
        self.assertIn('class="persona-state"', html)
        self.assertIn("กำลังดู", html)
        self.assertIn('class="search-leading"', html)
        self.assertIn('class="btn btn-primary btn-pill analyze-btn"', html)
        self.assertIn('id="consumerView"', html)
        self.assertIn('id="operatorView"', html)
        self.assertIn("เรื่องที่ควรรู้ก่อนไป", html)
        self.assertIn("จุดวิกฤตและจุดเฝ้าระวัง", html)
        self.assertNotIn("Top mentions", html)
        self.assertIn('id="consumerReviews"', html)
        self.assertIn('id="evidenceDrawer"', html)
        self.assertIn("รีวิวทั้งหมด", html)
        self.assertIn("R001", html)

    def test_renders_aspect_strengths_and_weaknesses_in_original_dashboard(self):
        payload = _payload()
        payload["aspect_summary"] = {
            "food": {"positive": 6, "neutral": 1, "negative": 3, "total": 10},
            "service": {"positive": 1, "neutral": 2, "negative": 7, "total": 10},
        }
        html = _get_dashboard(payload)
        self.assertIn("ร้านนี้เด่น/ด้อยเรื่องอะไร", html)
        self.assertIn('class="asp-chart"', html)
        self.assertIn('class="asp-card asp-row"', html)
        self.assertIn('class="asp-signal positive"', html)
        self.assertIn('class="asp-signal negative"', html)
        self.assertIn('data-aspect-open="aspect-panel-food"', html)
        self.assertIn('id="aspectModal"', html)
        self.assertIn('role="dialog"', html)
        self.assertIn("กดเพื่อดูเสียงลูกค้า", html)
        self.assertIn("ย่อกลับ", html)
        self.assertIn('class="asp-review-snippet evidence-trigger"', html)
        self.assertIn('data-evidence="R001"', html)
        self.assertIn("อ่านรีวิวเต็ม", html)
        self.assertNotIn('<details class="asp-card">', html)
        self.assertIn("เชิงบวก 60%", html)
        self.assertIn('class="section-number">02</div>', html)
        self.assertIn('class="section-number">04</div>', html)

    def test_warning_decision_summary_is_section_three(self):
        payload = _payload()
        payload["distribution"] = {
            "counts": {"positive": 3, "neutral": 3, "negative": 4},
            "total": 10,
            "pct": {"positive": 30, "neutral": 30, "negative": 40},
        }
        html = _get_dashboard(payload)
        self.assertIn("ควรอ่านข้อควรระวังก่อนตัดสินใจ", html)
        section_three = html.index('class="section-number">03</div>')
        verdict = html.index("ควรอ่านข้อควรระวังก่อนตัดสินใจ")
        self.assertLess(section_three, verdict)

    def test_operator_watchlist_closes_the_report(self):
        html = _get_dashboard(_payload())
        self.assertLess(
            html.index("แนวทางพัฒนาร้าน"),
            html.index("Priority watchlist"),
        )
        self.assertIn('class="model-menu"', html)
        self.assertIn('class="model-group sentiment-group"', html)
        self.assertIn('class="model-group extract-group"', html)
        self.assertIn('class="model-group-icon"', html)

    def test_long_analysis_result_is_scrollable_without_disclosure(self):
        payload = _payload()
        payload["reviews"] = payload["reviews"] * 6
        html = _get_dashboard(payload)
        self.assertIn('class="panel result-panel"', html)
        self.assertIn('class="tbl-wrap result-scroll"', html)
        self.assertNotIn('id="resultMoreBtn"', html)
        self.assertNotIn('data-result-extra=', html)

    def test_consumer_reviews_render_as_filterable_scroll_feed(self):
        payload = _payload()
        payload["reviews"] = payload["reviews"] * 6
        html = _get_dashboard(payload)
        self.assertIn('class="consumer-review-head"', html)
        self.assertIn('id="consumerReviewVisibleCount"', html)
        self.assertIn('aria-label="รายการรีวิวทั้งหมด"', html)
        self.assertIn('class="consumer-review-card-foot"', html)
        self.assertNotIn('id="consumerReviewsMoreBtn"', html)
        self.assertNotIn('data-consumer-extra=', html)


if __name__ == "__main__":
    unittest.main()
