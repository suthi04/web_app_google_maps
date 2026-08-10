"""Gemini extraction maps a (mocked) structured response into the dashboard contract,
and reports unavailable when there is no API key. No real API calls are made."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.phrases import llm_extract


class TestLLMExtract(unittest.TestCase):
    def test_unavailable_without_key(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False):
            self.assertFalse(llm_extract.available())

    def test_parse_response_to_contract(self):
        payload = {
            "reviews": [
                {"index": 0, "phrases": [
                    {"phrase": "อาหารแซ่บมาก", "aspect": "food", "sentiment": "positive"},
                    {"phrase": "รอนาน", "aspect": "service", "sentiment": "negative"},
                ]},
                {"index": 1, "phrases": [
                    {"phrase": "รอนาน", "aspect": "service", "sentiment": "negative"},
                ]},
            ]
        }
        contract = llm_extract._to_contract(payload)
        self.assertEqual(contract["food"]["positive"][0]["word"], "อาหารแซ่บมาก")
        neg = contract["service"]["negative"]
        self.assertEqual(neg[0]["word"], "รอนาน")
        self.assertEqual(neg[0]["count"], 2)   # merged across the two reviews
        self.assertEqual(neg[0]["review_count"], 2)
        self.assertEqual(neg[0]["evidence_review_ids"], ["R001", "R002"])

    def test_payload_occurrences_preserve_valid_review_index(self):
        payload = {"reviews": [
            {"index": 3, "phrases": [
                {"phrase": "บริการช้า", "aspect": "service", "sentiment": "negative"}
            ]},
            {"index": -1, "phrases": [
                {"phrase": "ต้องข้าม", "aspect": "food", "sentiment": "positive"}
            ]},
        ]}
        self.assertEqual(llm_extract.payload_occurrences(payload), [{
            "index": 3, "text": "บริการช้า",
            "aspect": "service", "sentiment": "negative",
        }])

    def test_long_sentences_are_dropped(self):
        """Gemini sometimes leaks a whole sentence instead of a concise phrase —
        guard against it so the dashboard chips stay short."""
        long_sentence = ("วันนี้พามาทานข้าวกับครอบครัวอาหารอร่อยทุกอย่าง"
                         "บริการก็ดีมากๆบรรยากาศร้านดีนั่งสบายมาก")
        self.assertGreater(len(long_sentence), llm_extract._MAX_PHRASE_CHARS)
        payload = {"reviews": [{"index": 0, "phrases": [
            {"phrase": "อาหารอร่อยมาก", "aspect": "food", "sentiment": "positive"},
            {"phrase": long_sentence, "aspect": "food", "sentiment": "positive"},
        ]}]}
        contract = llm_extract._to_contract(payload)
        words = [it["word"] for it in contract["food"]["positive"]]
        self.assertIn("อาหารอร่อยมาก", words)
        self.assertNotIn(long_sentence, words)

    def test_extract_all_uses_client_and_returns_contract(self):
        import json
        payload = {"reviews": [{"index": 0, "phrases": [
            {"phrase": "บริการดีมาก", "aspect": "service", "sentiment": "positive"}]}]}
        fake_resp = mock.Mock()
        fake_resp.text = json.dumps(payload)
        fake_client = mock.Mock()
        fake_client.models.generate_content.return_value = fake_resp
        with mock.patch.object(llm_extract, "_client", return_value=fake_client):
            out = llm_extract.extract_all([{"text": "บริการดีมาก"}])
        self.assertEqual(out["service"]["positive"][0]["word"], "บริการดีมาก")
        fake_client.models.generate_content.assert_called_once()

    def test_narrative_keeps_only_evidence_backed_items(self):
        reviews = [
            {"text": "อาหารอร่อยมาก แต่ช่วงเย็นรอคิวนาน 20 นาที"},
            {"text": "พนักงานบริการดีและแนะนำเมนูเก่ง"},
        ]
        payload = {"analysis": {
            "overview": {
                "headline": "อาหารเด่นแต่ควรเผื่อเวลารอ",
                "detail": "ลูกค้าชมอาหารและระบุว่าช่วงเย็นรอคิวนาน 20 นาที",
                "evidence_indices": [0],
                "evidence_quotes": ["อาหารอร่อยมาก", "รอคิวนาน 20 นาที"],
            },
            "visit_tips": [{
                "title": "ช่วงเย็นอาจต้องรอคิว",
                "detail": "มีรีวิวระบุว่ารอประมาณ 20 นาที",
                "advice": "ควรเผื่อเวลาก่อนไป",
                "aspect": "service", "sentiment": "negative",
                "evidence_indices": [0],
                "evidence_quotes": ["รอคิวนาน 20 นาที"],
            }, {
                "title": "มีที่จอดรถ 50 คัน",
                "detail": "จอดรถได้สะดวก",
                "advice": "ขับรถมาได้",
                "aspect": "ambience", "sentiment": "positive",
                "evidence_indices": [1],
                "evidence_quotes": ["มีที่จอดรถ 50 คัน"],
            }],
            "aspect_summaries": [],
            "actions": [],
        }}
        narrative = llm_extract.narrative_from_payload(payload, reviews)
        self.assertEqual(narrative["overview"]["evidence_review_ids"], ["R001"])
        self.assertEqual(len(narrative["visit_tips"]), 1)
        self.assertEqual(narrative["visit_tips"][0]["review_count"], 1)

    def test_phrase_not_present_in_cited_review_is_dropped(self):
        payload = {"reviews": [{"index": 0, "phrases": [{
            "phrase": "มีที่จอดรถ", "aspect": "ambience", "sentiment": "positive"
        }]}]}
        contract = llm_extract._to_contract(
            payload, reviews=[{"text": "อาหารอร่อยมาก"}]
        )
        self.assertEqual(contract["ambience"]["positive"], [])

    def test_visit_tip_cannot_invert_clear_quote_sentiment(self):
        reviews = [{"text": "พนักงานสุภาพและบริการดีมาก"}]
        payload = {"analysis": {
            "overview": {},
            "visit_tips": [{
                "title": "บริการแย่", "detail": "พนักงานไม่ใส่ใจ",
                "advice": "ควรระวัง", "aspect": "service",
                "sentiment": "negative", "evidence_indices": [0],
                "evidence_quotes": ["พนักงานสุภาพและบริการดีมาก"],
            }],
            "aspect_summaries": [], "actions": [],
        }}
        narrative = llm_extract.narrative_from_payload(payload, reviews)
        self.assertEqual(narrative["visit_tips"], [])


if __name__ == "__main__":
    unittest.main()
