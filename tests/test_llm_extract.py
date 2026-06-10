"""LLM extraction maps a (mocked) structured response into the dashboard contract,
and reports unavailable when there is no API key. No real API calls are made."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.phrases import llm_extract


class TestLLMExtract(unittest.TestCase):
    def test_unavailable_without_key(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False):
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

    def test_extract_all_uses_client_and_returns_contract(self):
        payload = {"reviews": [{"index": 0, "phrases": [
            {"phrase": "บริการดีมาก", "aspect": "service", "sentiment": "positive"}]}]}
        fake_msg = mock.Mock()
        fake_block = mock.Mock(); fake_block.type = "text"
        import json
        fake_block.text = json.dumps(payload)
        fake_msg.content = [fake_block]
        fake_client = mock.Mock()
        fake_client.messages.create.return_value = fake_msg
        with mock.patch.object(llm_extract, "_client", return_value=fake_client):
            out = llm_extract.extract_all([{"text": "บริการดีมาก"}])
        self.assertEqual(out["service"]["positive"][0]["word"], "บริการดีมาก")
        fake_client.messages.create.assert_called_once()
