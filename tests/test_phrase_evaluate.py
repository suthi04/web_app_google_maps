import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval import build_phrase_queue, phrase_evaluate, phrase_schema
from core.phrases import llm_extract


class TestBuildPhraseQueue(unittest.TestCase):
    def test_deduplicates_and_is_seeded(self):
        records = [
            {"text": "อาหารอร่อย", "source": {"kind": "a"}},
            {"text": "อาหารอร่อย", "source": {"kind": "b"}},
            {"text": "บริการช้า", "source": {"kind": "a"}},
        ]
        a = build_phrase_queue.build_queue(records, seed=7)
        b = build_phrase_queue.build_queue(records, seed=7)
        self.assertEqual(a, b)
        self.assertEqual(len(a["reviews"]), 2)
        phrase_schema.validate_document(a, require_phrases=False)

    def test_unique_phrases_for_adjudication(self):
        from eval import phrase_adjudicate
        first = {"text": "อร่อย", "start": 5, "end": 10,
                 "aspect": "food", "sentiment": "positive"}
        duplicate = dict(first)
        self.assertEqual(phrase_adjudicate.unique_phrases([first], [duplicate]), [first])


class TestRulePhrasePrediction(unittest.TestCase):
    def test_predictions_have_source_spans_and_labels(self):
        text = "อาหารอร่อยมาก แต่บริการช้า"
        predictions = phrase_evaluate.predict_rule(text)
        self.assertTrue(predictions)
        self.assertTrue(any(p["aspect"] == "food" for p in predictions))
        self.assertTrue(any(p["aspect"] == "service" for p in predictions))
        for phrase in predictions:
            self.assertGreaterEqual(phrase["start"], 0)
            self.assertEqual(text[phrase["start"]:phrase["end"]], phrase["text"])
            self.assertIn(phrase["sentiment"], phrase_schema.SENTIMENTS)

    def test_locate_phrase_matches_through_spaces_and_punctuation(self):
        text = "อาหาร อร่อยมาก!"
        self.assertEqual(
            phrase_evaluate.locate_phrase(text, ["อาหารอร่อยมาก"], set()),
            (0, 14),
        )

    def test_build_report_end_to_end(self):
        text = "อาหารอร่อย"
        rid = phrase_schema.review_id(text)
        gold = {
            "schema_version": 1,
            "reviews": [{
                "id": rid,
                "text": text,
                "phrases": [{
                    "text": text,
                    "start": 0,
                    "end": len(text),
                    "aspect": "food",
                    "sentiment": "positive",
                }],
            }],
        }
        report = phrase_evaluate.build_report(gold)
        self.assertEqual(report["exact"]["f1"], 1.0)
        self.assertEqual(report["partial_joint"]["f1"], 1.0)
        self.assertEqual(report["unaligned_predictions"], 0)


class TestLLMPhrasePrediction(unittest.TestCase):
    def test_payload_maps_back_to_review_span(self):
        text = "อาหารอร่อย แต่บริการช้า"
        reviews = [{"id": phrase_schema.review_id(text), "text": text}]
        payload = {"reviews": [{"index": 0, "phrases": [{
            "phrase": "บริการช้า", "aspect": "service", "sentiment": "negative",
        }]}]}
        predictions = phrase_evaluate.predictions_from_llm_payload(reviews, payload)
        item = predictions[reviews[0]["id"]][0]
        self.assertEqual(text[item["start"]:item["end"]], "บริการช้า")

    def test_llm_dataset_is_chunked_without_real_api(self):
        reviews = []
        for text in ("อาหารอร่อย", "บริการช้า", "ร้านสะอาด"):
            reviews.append({"id": phrase_schema.review_id(text), "text": text})
        payloads = [
            {"reviews": [{"index": 0, "phrases": []}, {"index": 1, "phrases": []}]},
            {"reviews": [{"index": 0, "phrases": []}]},
        ]
        with mock.patch.object(llm_extract, "available", return_value=True), \
             mock.patch.object(llm_extract, "extract_payload", side_effect=payloads) as call:
            result = phrase_evaluate.predict_dataset(
                reviews, engine="llm", llm_batch_size=2
            )
        self.assertEqual(call.call_count, 2)
        self.assertEqual(set(result), {review["id"] for review in reviews})


if __name__ == "__main__":
    unittest.main()
