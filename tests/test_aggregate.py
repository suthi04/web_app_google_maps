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

    def _mk(self, aspect, sentiment, agg_key, display, label=None):
        from core.phrases.model import Phrase
        p = Phrase(surface=display)
        p.aspect, p.sentiment = aspect, sentiment
        p.agg_key, p.display = agg_key, display
        p.label = label or display
        return p

    def test_repeats_merge_into_one_count(self):
        from core.phrases.aggregate import build
        phrases = [
            self._mk("service", "negative", "รอนาน", "รอนาน"),
            self._mk("service", "negative", "รอนาน", "รออาหารนาน"),
            self._mk("service", "negative", "รอนาน", "รอนาน"),
        ]
        out = build(phrases)
        neg = out["service"]["negative"]
        self.assertEqual(len(neg), 1)
        self.assertEqual(neg[0]["count"], 3)
        # label = most frequent display ("รอนาน" appears 2x vs "รออาหารนาน" 1x)
        self.assertEqual(neg[0]["word"], "รอนาน")


if __name__ == "__main__":
    unittest.main()
