import json
import os
import unittest

from eval import evaluate


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHALLENGE_PATH = os.path.join(ROOT, "data", "sentiment_challenge_reviews.json")


class SentimentChallengeDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(CHALLENGE_PATH, encoding="utf-8") as handle:
            cls.document = json.load(handle)
        cls.reviews = cls.document["reviews"]

    def test_dataset_is_balanced_and_unique(self):
        self.assertEqual(self.document["kind"], "sentiment_challenge")
        self.assertEqual(len(self.reviews), 90)
        self.assertEqual(len({item["id"] for item in self.reviews}), 90)
        self.assertEqual(len({item["text"] for item in self.reviews}), 90)
        for label in evaluate.LABELS:
            self.assertEqual(
                sum(item["label"] == label for item in self.reviews),
                30,
            )

    def test_provenance_and_edge_case_coverage_are_explicit(self):
        self.assertTrue(all(item["source"] == "curated_challenge" for item in self.reviews))
        self.assertGreaterEqual(
            sum("slang" in item["tags"] for item in self.reviews),
            20,
        )
        self.assertGreaterEqual(
            sum("factual" in item["tags"] for item in self.reviews),
            20,
        )
        self.assertGreaterEqual(
            sum("negation" in item["tags"] for item in self.reviews),
            10,
        )

    def test_evaluator_can_load_custom_dataset_without_changing_gold_default(self):
        challenge = evaluate.load_dataset(CHALLENGE_PATH)
        gold = evaluate.load_dataset()
        self.assertEqual(len(challenge), 90)
        self.assertNotEqual(CHALLENGE_PATH, os.path.join(ROOT, "data", "labeled_reviews.json"))
        self.assertGreater(len(gold), 0)


if __name__ == "__main__":
    unittest.main()
