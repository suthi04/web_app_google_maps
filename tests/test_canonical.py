import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.phrases.model import Phrase
from core.phrases import canonical


class TestCanonical(unittest.TestCase):
    def test_bound_phrase(self):
        p = Phrase(surface="อาหาร อร่อย มากๆ", head_noun="อาหาร",
                   descriptor_tokens=["อร่อย"], pattern="P1")
        self.assertEqual(canonical.canonicalize(p).canonical, "อาหารอร่อย")

    def test_negation_kept(self):
        p = Phrase(surface="ราคา ไม่ แพง", head_noun="ราคา",
                   descriptor_tokens=["ไม่", "แพง"], pattern="P2")
        self.assertEqual(canonical.canonicalize(p).canonical, "ราคาไม่แพง")

    def test_compound_descriptor_no_synthesis(self):
        p = Phrase(surface="เย็น สบาย", descriptor_tokens=["เย็น", "สบาย"],
                   pattern="P7", aspect="atmosphere", aspect_conf="high")
        self.assertEqual(canonical.canonicalize(p).canonical, "เย็นสบาย")

    def test_bare_descriptor_synthesizes_head_noun(self):
        p = Phrase(surface="อร่อย", descriptor_tokens=["อร่อย"], pattern="P7",
                   aspect="food", aspect_conf="high")
        self.assertEqual(canonical.canonicalize(p).canonical, "อาหารอร่อย")

    def test_hinted_single_descriptor_not_synthesized(self):
        p = Phrase(surface="คึกคัก", descriptor_tokens=["คึกคัก"], pattern="P7",
                   aspect="atmosphere", aspect_conf="high")
        self.assertEqual(canonical.canonicalize(p).canonical, "คึกคัก")

    def test_idiom_uses_canonical_map(self):
        p = Phrase(surface="ริมน้ำ", pattern="idiom")
        self.assertEqual(canonical.canonicalize(p).canonical, "ติดริมน้ำ")

    def test_defensive_intensifier_strip(self):
        p = Phrase(surface="อาหาร อร่อย", head_noun="อาหาร",
                   descriptor_tokens=["อร่อย", "มาก"], pattern="P1")
        self.assertEqual(canonical.canonicalize(p).canonical, "อาหารอร่อย")


if __name__ == "__main__":
    unittest.main()
