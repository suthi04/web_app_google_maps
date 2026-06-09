import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.phrases import extract


class TestGrammar(unittest.TestCase):
    def test_p1_noun_plus_descriptor(self):
        out = extract._match_grammar(["อาหาร", "อร่อย", "มากๆ"], [False] * 3, {})
        p = out[0]
        self.assertEqual(p.head_noun, "อาหาร")
        self.assertIn("อร่อย", p.descriptor_tokens)
        self.assertNotIn("มากๆ", p.descriptor_tokens)   # intensifier excluded
        self.assertEqual(p.pattern, "P1")

    def test_p2_negation(self):
        out = extract._match_grammar(["ราคา", "ไม่", "แพง"], [False] * 3, {})
        p = out[0]
        self.assertEqual(p.head_noun, "ราคา")
        self.assertEqual(p.descriptor_tokens, ["ไม่", "แพง"])
        self.assertEqual(p.pattern, "P2")

    def test_p3_lexicon_phrase_recovery(self):
        out = extract._match_grammar(["รอ", "นาน"], [False] * 2, {})
        p = out[0]
        self.assertIsNone(p.head_noun)
        self.assertEqual(p.descriptor_tokens, ["รอนาน"])
        self.assertEqual(p.pattern, "P3")

    def test_b3_standalone_hinted_descriptor(self):
        out = extract._match_grammar(["คึกคัก"], [False], {})
        self.assertEqual(out[0].descriptor_tokens, ["คึกคัก"])
        self.assertEqual(out[0].pattern, "P7")

    def test_b3_standalone_polar_descriptor(self):
        out = extract._match_grammar(["อร่อย"], [False], {})
        self.assertEqual(out[0].descriptor_tokens, ["อร่อย"])
        self.assertEqual(out[0].pattern, "P7")

    def test_bare_noun_not_emitted(self):
        out = extract._match_grammar(["อาหาร"], [False], {})
        self.assertEqual(out, [])

    def test_respects_used_flags(self):
        out = extract._match_grammar(["อาหาร", "อร่อย"], [True, True], {})
        self.assertEqual(out, [])
