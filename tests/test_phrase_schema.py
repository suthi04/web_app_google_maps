import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval import phrase_schema


class TestPhraseSchema(unittest.TestCase):
    def test_review_id_is_stable_across_whitespace(self):
        self.assertEqual(
            phrase_schema.review_id("อาหารอร่อย   มาก"),
            phrase_schema.review_id("อาหารอร่อย มาก"),
        )

    def test_find_occurrences_includes_repeated_phrase(self):
        self.assertEqual(
            phrase_schema.find_occurrences("ดีมากและดีมาก", "ดีมาก"),
            [(0, 5), (8, 13)],
        )

    def test_valid_document(self):
        text = "อาหารอร่อย"
        doc = {
            "schema_version": 1,
            "reviews": [{
                "id": phrase_schema.review_id(text),
                "text": text,
                "phrases": [{
                    "text": "อร่อย", "start": 5, "end": 10,
                    "aspect": "food", "sentiment": "positive",
                }],
            }],
        }
        phrase_schema.validate_document(doc)

    def test_rejects_text_span_mismatch(self):
        text = "อาหารอร่อย"
        doc = {
            "schema_version": 1,
            "reviews": [{
                "id": phrase_schema.review_id(text), "text": text,
                "phrases": [{
                    "text": "บริการ", "start": 5, "end": 10,
                    "aspect": "food", "sentiment": "positive",
                }],
            }],
        }
        with self.assertRaisesRegex(ValueError, "does not match"):
            phrase_schema.validate_document(doc)

    def test_queue_can_omit_phrases(self):
        text = "อาหารอร่อย"
        phrase_schema.validate_document({
            "schema_version": 1,
            "reviews": [{"id": phrase_schema.review_id(text), "text": text}],
        }, require_phrases=False)


if __name__ == "__main__":
    unittest.main()
