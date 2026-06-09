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


if __name__ == "__main__":
    unittest.main()
