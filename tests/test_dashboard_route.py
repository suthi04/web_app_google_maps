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


class TestNoDeadJsonBlob(unittest.TestCase):
    def test_analysis_data_script_removed(self):
        html = _get_dashboard(_payload())
        self.assertNotIn('id="analysis-data"', html)


class TestAudienceDashboard(unittest.TestCase):
    def test_renders_consumer_and_operator_persona_tabs(self):
        html = _get_dashboard(_payload())
        self.assertIn("สำหรับผู้บริโภค", html)
        self.assertIn("สำหรับผู้ประกอบการ", html)
        self.assertIn('id="consumerView"', html)
        self.assertIn('id="operatorView"', html)
        self.assertIn("เรื่องที่ควรรู้ก่อนไป", html)
        self.assertIn("จุดวิกฤตและจุดเฝ้าระวัง", html)
        self.assertNotIn("Top mentions", html)
        self.assertIn('id="consumerReviews"', html)
        self.assertIn('id="evidenceDrawer"', html)
        self.assertIn("รีวิวทั้งหมด", html)
        self.assertIn("R001", html)

    def test_operator_watchlist_closes_the_report(self):
        html = _get_dashboard(_payload())
        self.assertLess(
            html.index("แนวทางพัฒนาร้าน"),
            html.index("Priority watchlist"),
        )
        self.assertIn('class="model-menu"', html)

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
