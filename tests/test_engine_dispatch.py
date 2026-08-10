import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from core import pipeline
from core.phrases import llm_extract


class TestEngineDispatch(unittest.TestCase):
    # _phrase_pipeline returns (contract, engine_used, narrative). engine_used reflects the
    # engine that ACTUALLY produced the result — never the merely-selected one.
    def test_rule_engine_used_by_default(self):
        with mock.patch.object(config, "get_extract_engine", return_value="rule"), \
             mock.patch.object(llm_extract, "extract_all",
                               side_effect=AssertionError("LLM must not run")):
            _, engine, narrative = pipeline._phrase_pipeline([])   # must not call llm_extract
        self.assertEqual(engine, "rule")
        self.assertEqual(narrative, {})

    def test_llm_engine_used_on_success(self):
        with mock.patch.object(config, "get_extract_engine", return_value="llm"), \
             mock.patch.object(llm_extract, "available", return_value=True), \
             mock.patch.object(llm_extract, "extract_bundle", return_value=(
                 {"food": {"positive": []}}, {"overview": {"headline": "ดี"}}
             )):
            out, engine, narrative = pipeline._phrase_pipeline([{"text": "อร่อย"}])
        self.assertEqual(out["food"]["positive"], [])
        self.assertEqual(engine, "llm")
        self.assertEqual(narrative["overview"]["headline"], "ดี")

    def test_llm_engine_falls_back_when_unavailable(self):
        with mock.patch.object(config, "get_extract_engine", return_value="llm"), \
             mock.patch.object(llm_extract, "available", return_value=False), \
             mock.patch.object(pipeline, "_rule_phrase_pipeline",
                               return_value={"food": {}}) as rule:
            out, engine, narrative = pipeline._phrase_pipeline([{"clauses": []}])
        rule.assert_called_once()
        self.assertEqual(out, {"food": {}})
        self.assertEqual(engine, "rule")
        self.assertEqual(narrative, {})

    def test_llm_engine_falls_back_on_api_error(self):
        # selected=llm AND available, but the API call fails (e.g. 429 quota) ->
        # must fall back to rule AND report engine "rule", not "llm" (the bug)
        with mock.patch.object(config, "get_extract_engine", return_value="llm"), \
             mock.patch.object(llm_extract, "available", return_value=True), \
             mock.patch.object(llm_extract, "extract_bundle",
                               side_effect=RuntimeError("api down")), \
             mock.patch.object(pipeline, "_rule_phrase_pipeline",
                               return_value={"food": {}}) as rule:
            out, engine, narrative = pipeline._phrase_pipeline([{"clauses": []}])
        rule.assert_called_once()
        self.assertEqual(out, {"food": {}})
        self.assertEqual(engine, "rule")
        self.assertEqual(narrative, {})

    def test_gemini_contract_is_safely_supplemented_by_rule_evidence(self):
        gemini = {"food": {"positive": [{
            "word": "อาหารอร่อย", "count": 1,
            "evidence_review_ids": ["R001"],
        }], "neutral": [], "negative": []}}
        rule = {"food": {"positive": [{
            "word": "อาหารอร่อย", "count": 1,
            "evidence_review_ids": ["R001", "R002"],
        }], "neutral": [], "negative": [{
            "word": "อาหารช้า", "count": 1,
            "evidence_review_ids": ["R003"],
        }]}}
        merged = pipeline._merge_keyword_contracts(gemini, rule)
        positive = merged["food"]["positive"][0]
        self.assertEqual(positive["evidence_review_ids"], ["R001", "R002"])
        self.assertEqual(positive["review_count"], 2)
        self.assertEqual(merged["food"]["negative"][0]["word"], "อาหารช้า")
