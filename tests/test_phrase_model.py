import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.phrases.model import Phrase


class TestPhraseModel(unittest.TestCase):
    def test_defaults(self):
        p = Phrase(surface="อาหาร อร่อย")
        self.assertEqual(p.surface, "อาหาร อร่อย")
        self.assertIsNone(p.head_noun)
        self.assertEqual(p.descriptor_tokens, [])
        self.assertEqual(p.aspect_conf, "low")
        self.assertEqual(p.clause, {})

    def test_independent_mutable_defaults(self):
        a, b = Phrase(surface="x"), Phrase(surface="y")
        a.descriptor_tokens.append("อร่อย")
        self.assertEqual(b.descriptor_tokens, [])  # no shared mutable default


if __name__ == "__main__":
    unittest.main()
