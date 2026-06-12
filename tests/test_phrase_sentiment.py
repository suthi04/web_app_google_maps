import os, sys, unittest
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from core.phrases.model import Phrase
from core import sentiment


class TestPhraseSentiment(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(config, "get_use_model", return_value=False)
        p.start(); self.addCleanup(p.stop)

    def test_positive_descriptor_backstop(self):
        ph = Phrase(surface="อาหาร อร่อย", descriptor_tokens=["อร่อย"],
                    clause={"clean": "อาหารอร่อย", "tokens": ["อาหาร", "อร่อย"]})
        self.assertEqual(sentiment.classify_phrase(ph), "positive")

    def test_negative_descriptor_backstop(self):
        ph = Phrase(surface="รอ นาน", descriptor_tokens=["รอนาน"],
                    clause={"clean": "รอนาน", "tokens": ["รอนาน"]})
        self.assertEqual(sentiment.classify_phrase(ph), "negative")

    def test_ambiguous_phrase_uses_clause_context_not_phrase(self):
        ph = Phrase(surface="คน เยอะ", descriptor_tokens=["เยอะ"],
                    clause={"clean": "คนเยอะแต่บริการแย่", "tokens": ["คนเยอะ", "บริการแย่"]})
        self.assertEqual(sentiment.classify_phrase(ph), "negative")

    def test_clear_polarity_overrides_clause_majority(self):
        # "ราคาแพง" (ลบชัดเจน) ในอนุประโยคที่บวกเป็นส่วนใหญ่ ต้องยังเป็น negative
        clause = {"clean": "อาหารอร่อยรสชาติดีราคาแพง",
                  "tokens": ["อาหาร", "อร่อย", "รสชาติ", "ดี", "ราคา", "แพง"]}
        ph = Phrase(surface="ราคา แพง", head_noun="ราคา",
                    descriptor_tokens=["แพง"], clause=clause)
        self.assertEqual(sentiment.classify_phrase(ph), "negative")

    def test_negation_flips_to_positive(self):
        # "ราคาไม่แพง" -> positive แม้บริบทจะปนลบ (negation พลิกขั้ว)
        ph = Phrase(surface="ราคา ไม่ แพง", head_noun="ราคา",
                    descriptor_tokens=["ไม่", "แพง"],
                    clause={"clean": "ราคาไม่แพงแต่บริการแย่", "tokens": ["ราคาไม่แพง", "บริการแย่"]})
        self.assertEqual(sentiment.classify_phrase(ph), "positive")

    def test_ambiguous_phrase_reuses_clause_sentiment_no_model_call(self):
        from unittest import mock
        from core import sentiment
        from core.phrases.model import Phrase
        # ambiguous phrase: no own polarity -> would normally hit context/model
        p = Phrase(surface="คนเยอะ", descriptor_tokens=["คนเยอะ"])
        p.clause = {"clean": "คนเยอะ", "tokens": ["คนเยอะ"], "sentiment": "negative"}
        with mock.patch.object(sentiment, "_predict_model",
                               side_effect=AssertionError("model must not be called")):
            self.assertEqual(sentiment.classify_phrase(p), "negative")


if __name__ == "__main__":
    unittest.main()
