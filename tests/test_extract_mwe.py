import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.phrases import extract


class TestMWE(unittest.TestCase):
    def test_matches_multitoken_idiom(self):
        phrases, used = extract._match_mwes(["ติด", "ริมน้ำ"], {})
        self.assertIn("ติดริมน้ำ", [p.surface for p in phrases])
        self.assertEqual(phrases[0].pattern, "idiom")
        self.assertTrue(all(used))

    def test_matches_single_token_idiom(self):
        phrases, used = extract._match_mwes(["ริมน้ำ"], {})
        self.assertEqual(phrases[0].surface, "ริมน้ำ")
        self.assertEqual(phrases[0].pattern, "idiom")

    def test_matches_descriptor_compound(self):
        phrases, used = extract._match_mwes(["เย็น", "สบาย"], {})
        p = phrases[0]
        self.assertEqual(p.surface, "เย็นสบาย")
        self.assertEqual(p.pattern, "P7")
        self.assertEqual(p.descriptor_tokens, ["เย็นสบาย"])
        self.assertEqual(p.aspect, "atmosphere")

    def test_no_mwe_returns_empty(self):
        phrases, used = extract._match_mwes(["อาหาร", "อร่อย"], {})
        self.assertEqual(phrases, [])
        self.assertEqual(used, [False, False])
