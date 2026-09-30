"""Verify that the balanced research set contains unchanged source reviews."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import unittest

from core.preprocess import is_thai
from eval.evaluate import load_evaluation_document

ROOT = Path(__file__).resolve().parents[1]


class PupenDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = load_evaluation_document(ROOT / "data/labeled_reviews.json")

    def test_main_file_contains_only_review_text_and_labels(self):
        main = json.loads((ROOT / "data/labeled_reviews.json").read_text(encoding="utf-8"))
        self.assertEqual(set(main), {"reviews"})
        self.assertTrue(all(set(row) == {"text", "label"} for row in main["reviews"]))

    def test_balanced_unique_and_ai_annotation_disclosed(self):
        rows = self.document["reviews"]
        self.assertEqual(Counter(row["label"] for row in rows), {"positive": 20, "neutral": 20, "negative": 20})
        self.assertEqual(len({row["id"] for row in rows}), 60)
        self.assertEqual(len({" ".join(row["text"].split()) for row in rows}), 60)
        self.assertEqual(self.document["kind"], "real_review_sentiment_ai_annotated_pilot")
        self.assertIsNone(self.document["meta"]["annotation"]["inter_annotator_agreement"])
        self.assertTrue(all(row["annotation"]["human_validated"] is False for row in rows))

    def test_every_text_matches_its_google_maps_source(self):
        for row in self.document["reviews"]:
            with self.subTest(id=row["id"]):
                source = row["source"]
                document = json.loads((ROOT / source["collection_file"]).read_text(encoding="utf-8"))
                raw = document["reviews"][source["source_index"]]
                self.assertEqual(row["text"], raw["text"])
                self.assertEqual(source["review_id"], raw["reviewId"])
                self.assertEqual(source["place_id"], "ChIJ6d7RdwSUAjERrnAUJW-I23Q")
                self.assertEqual(raw["originalLanguage"], "th")
                self.assertEqual(raw["reviewOrigin"], "Google")
                self.assertTrue(is_thai(row["text"], threshold=0.5))
                self.assertEqual(hashlib.sha256(row["text"].encode()).hexdigest(), source["text_sha256"])


if __name__ == "__main__":
    unittest.main()
