import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.phrases.model import Phrase
from core.phrases import synonyms


def _p(canonical):
    return Phrase(surface=canonical, canonical=canonical)


class TestSynonyms(unittest.TestCase):
    def test_price_variants_merge(self):
        a = synonyms.aggregate(_p("ราคาไม่แพง"))
        b = synonyms.aggregate(_p("คุ้มค่า"))
        self.assertEqual(a.concept, b.concept)
        self.assertEqual(a.label, "ราคาคุ้มค่า")

    def test_antonyms_do_not_merge(self):
        good = synonyms.aggregate(_p("ราคาไม่แพง"))
        bad = synonyms.aggregate(_p("ราคาแพง"))
        self.assertNotEqual(good.concept, bad.concept)

    def test_distinct_descriptors_stay_separate(self):
        a = synonyms.aggregate(_p("อร่อย"))
        b = synonyms.aggregate(_p("จัดจ้าน"))
        self.assertNotEqual(a.concept, b.concept)
        self.assertEqual(a.concept, "อร่อย")   # identity when ungrouped
        self.assertEqual(a.label, "อร่อย")

    def test_ungrouped_identity(self):
        p = synonyms.aggregate(_p("ปลาสด"))
        self.assertEqual((p.concept, p.label), ("ปลาสด", "ปลาสด"))


if __name__ == "__main__":
    unittest.main()
