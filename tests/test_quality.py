import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.phrases.model import Phrase
from core.phrases import quality


class TestQuality(unittest.TestCase):
    def test_keeps_bound_phrase(self):
        p = Phrase(surface="อาหาร อร่อย", head_noun="อาหาร",
                   descriptor_tokens=["อร่อย"], pattern="P1")
        self.assertEqual(len(quality.filter_phrases([p], ["food"])), 1)

    def test_rejects_meta_verb(self):
        p = Phrase(surface="แนะนำ", descriptor_tokens=["แนะนำ"], pattern="P7")
        self.assertEqual(quality.filter_phrases([p], ["food"]), [])

    def test_rejects_bare_noun(self):
        p = Phrase(surface="อาหาร", head_noun="อาหาร", descriptor_tokens=[], pattern="P1")
        self.assertEqual(quality.filter_phrases([p], ["food"]), [])

    def test_keeps_descriptor_compound(self):
        p = Phrase(surface="เย็น สบาย", descriptor_tokens=["เย็น", "สบาย"], pattern="P7")
        out = quality.filter_phrases([p], ["food", "atmosphere"])
        self.assertEqual(len(out), 1)

    def test_keeps_hinted_single_descriptor(self):
        p = Phrase(surface="คึกคัก", descriptor_tokens=["คึกคัก"], pattern="P7")
        out = quality.filter_phrases([p], ["food", "atmosphere"])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].aspect, "atmosphere")

    def test_bare_descriptor_high_conf_single_clause_aspect(self):
        p = Phrase(surface="ดี", descriptor_tokens=["ดี"], pattern="P7")
        out = quality.filter_phrases([p], ["atmosphere"])
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0].aspect, out[0].aspect_conf), ("atmosphere", "high"))

    def test_bare_descriptor_low_conf_dropped(self):
        p = Phrase(surface="ดี", descriptor_tokens=["ดี"], pattern="P7")
        self.assertEqual(quality.filter_phrases([p], ["food", "atmosphere"]), [])

    def test_idiom_always_kept(self):
        p = Phrase(surface="ติดริมน้ำ", pattern="idiom")
        self.assertEqual(len(quality.filter_phrases([p], [])), 1)


if __name__ == "__main__":
    unittest.main()
