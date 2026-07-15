import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval import phrase_dataset, phrase_error_analysis, phrase_schema


def _review(text, phrases):
    return {"id": phrase_schema.review_id(text), "text": text, "phrases": phrases}


def _phrase(text, start, end, aspect="food", sentiment="positive"):
    return {"text": text[start:end], "start": start, "end": end,
            "aspect": aspect, "sentiment": sentiment}


class TestPhraseDataset(unittest.TestCase):
    def setUp(self):
        self.reviews = [
            _review("อาหารอร่อย", [_phrase("อาหารอร่อย", 0, 10)]),
            _review("บริการช้า", [_phrase("บริการช้า", 0, 9, "service", "negative")]),
            _review("ร้านเปิดสิบโมง", []),
            _review("บรรยากาศดี", [_phrase("บรรยากาศดี", 0, 11, "ambience")]),
        ]
        self.doc = {"schema_version": 1, "kind": "phrase_gold", "reviews": self.reviews}

    def test_dataset_stats(self):
        stats = phrase_dataset.dataset_stats(self.doc)
        self.assertEqual(stats["reviews_total"], 4)
        self.assertEqual(stats["phrases_total"], 3)
        self.assertEqual(stats["reviews_without_phrases"], 1)
        self.assertEqual(stats["aspect_counts"]["service"], 1)

    def test_split_is_deterministic_and_has_no_leakage(self):
        first = phrase_dataset.split_document(
            self.doc, train_ratio=0.5, dev_ratio=0.25, seed=9
        )
        second = phrase_dataset.split_document(
            self.doc, train_ratio=0.5, dev_ratio=0.25, seed=9
        )
        self.assertEqual(first, second)
        phrase_dataset.assert_no_leakage(first)
        self.assertEqual(sum(len(x["reviews"]) for x in first.values()), 4)

    def test_invalid_ratios_rejected(self):
        with self.assertRaises(ValueError):
            phrase_dataset.split_document(self.doc, train_ratio=0.9, dev_ratio=0.2)


class TestPhraseErrorAnalysis(unittest.TestCase):
    def test_classifies_boundary_label_fp_and_fn_errors(self):
        text = "อาหารอร่อยบริการช้า"
        rid = phrase_schema.review_id(text)
        gold_phrases = [
            _phrase(text, 0, 10),
            _phrase(text, 10, len(text), "service", "negative"),
        ]
        predictions = [{
            "text": text[1:10], "start": 1, "end": 10,
            "aspect": "service", "sentiment": "negative",
        }, {
            "text": "เกิน", "start": 30, "end": 33,
            "aspect": "food", "sentiment": "neutral",
        }]
        report = phrase_error_analysis.analyze_errors(
            {"schema_version": 1, "reviews": [_review(text, gold_phrases)]},
            {rid: predictions},
        )
        summary = report["summary"]
        self.assertEqual(summary["boundary_errors"], 1)
        self.assertEqual(summary["aspect_errors"], 1)
        self.assertEqual(summary["sentiment_errors"], 1)
        self.assertEqual(summary["false_negatives"], 1)
        self.assertEqual(summary["false_positives"], 1)


if __name__ == "__main__":
    unittest.main()
