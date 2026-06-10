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

    def test_self_contained_descriptor_not_synthesized(self):
        # คึกคัก reads naturally alone (in NO_SYNTH_DESCRIPTORS) -> not "บรรยากาศคึกคัก"
        p = Phrase(surface="คึกคัก", descriptor_tokens=["คึกคัก"], pattern="P7",
                   aspect="atmosphere", aspect_conf="high")
        self.assertEqual(canonical.canonicalize(p).canonical, "คึกคัก")

    def test_service_bare_descriptor_synthesized(self):
        # ช้า is NOT self-contained -> synthesize head noun so it is not bare noise
        p = Phrase(surface="ช้า", descriptor_tokens=["ช้า"], pattern="P7",
                   aspect="service", aspect_conf="high")
        self.assertEqual(canonical.canonicalize(p).canonical, "บริการช้า")

    def test_idiom_uses_canonical_map(self):
        p = Phrase(surface="ริมน้ำ", pattern="idiom")
        self.assertEqual(canonical.canonicalize(p).canonical, "ติดริมน้ำ")

    def test_defensive_intensifier_strip(self):
        p = Phrase(surface="อาหาร อร่อย", head_noun="อาหาร",
                   descriptor_tokens=["อร่อย", "มาก"], pattern="P1")
        self.assertEqual(canonical.canonicalize(p).canonical, "อาหารอร่อย")

    def test_display_keeps_intensifier(self):
        from core.phrases.model import Phrase
        from core.phrases.canonical import canonicalize
        p = Phrase(surface="บริการ ดี มาก", head_noun="บริการ",
                   descriptor_tokens=["ดี", "มาก"], pattern="P1")
        canonicalize(p)
        self.assertEqual(p.display, "บริการดีมาก")
        self.assertEqual(p.canonical, "บริการดี")   # key strips intensifier

    def test_no_oversynthesis_when_head_noun_present(self):
        from core.phrases.model import Phrase
        from core.phrases.canonical import canonicalize
        p = Phrase(surface="บริการ รอนาน", head_noun="บริการ",
                   descriptor_tokens=["รอนาน"], pattern="P1")
        canonicalize(p)
        self.assertEqual(p.display, "บริการรอนาน")
        self.assertEqual(p.canonical, "บริการรอนาน")

    def test_bare_lone_descriptor_still_synthesized(self):
        from core.phrases.model import Phrase
        from core.phrases.canonical import canonicalize
        p = Phrase(surface="อร่อย", descriptor_tokens=["อร่อย"], pattern="P7",
                   aspect="food", aspect_conf="high")
        canonicalize(p)
        self.assertEqual(p.canonical, "อาหารอร่อย")
        self.assertEqual(p.display, "อาหารอร่อย")


if __name__ == "__main__":
    unittest.main()
