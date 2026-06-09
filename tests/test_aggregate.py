import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.phrases.model import Phrase
from core.phrases import aggregate


def _ph(concept, label, aspect, sentiment):
    return Phrase(surface=label, canonical=label, concept=concept, label=label,
                  aspect=aspect, sentiment=sentiment)


class TestAggregate(unittest.TestCase):
    def test_shape_and_counts(self):
        # aggregate uses dashboard contract keys (food/service/ambience);
        # pipeline maps "atmosphere" -> "ambience" before this stage.
        phrases = [
            _ph("อาหารอร่อย", "อาหารอร่อย", "food", "positive"),
            _ph("อาหารอร่อย", "อาหารอร่อย", "food", "positive"),
            _ph("price_good", "ราคาคุ้มค่า", "food", "positive"),
            _ph("รอนาน", "รอนาน", "service", "negative"),
        ]
        out = aggregate.build(phrases)
        self.assertEqual(set(out), {"food", "service", "ambience"})
        self.assertEqual(set(out["food"]), {"positive", "neutral", "negative"})
        food_pos = {d["word"]: d["count"] for d in out["food"]["positive"]}
        self.assertEqual(food_pos["อาหารอร่อย"], 2)
        self.assertEqual(food_pos["ราคาคุ้มค่า"], 1)

    def test_same_concept_splits_across_sentiment(self):
        phrases = [
            _ph("คนเยอะ", "คนเยอะ", "ambience", "positive"),
            _ph("คนเยอะ", "คนเยอะ", "ambience", "negative"),
        ]
        out = aggregate.build(phrases)
        self.assertEqual(out["ambience"]["positive"][0]["count"], 1)
        self.assertEqual(out["ambience"]["negative"][0]["count"], 1)

    def test_drops_uncategorized_and_unsented(self):
        phrases = [_ph("x", "x", None, "positive"), _ph("y", "y", "food", None)]
        out = aggregate.build(phrases)
        self.assertEqual(out["food"]["positive"], [])


if __name__ == "__main__":
    unittest.main()
