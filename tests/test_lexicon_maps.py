import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import lexicon


class TestLexiconMaps(unittest.TestCase):
    def test_noun_to_aspect(self):
        self.assertEqual(lexicon.NOUN_TO_ASPECT["ราคา"], "food")   # Price-into-Food
        self.assertEqual(lexicon.NOUN_TO_ASPECT["พนักงาน"], "service")
        self.assertEqual(lexicon.NOUN_TO_ASPECT["บรรยากาศ"], "atmosphere")

    def test_aspect_head_noun(self):
        self.assertEqual(lexicon.ASPECT_HEAD_NOUN["food"], "อาหาร")
        self.assertEqual(set(lexicon.ASPECT_HEAD_NOUN), {"food", "service", "atmosphere"})

    def test_idioms(self):
        self.assertEqual(lexicon.IDIOMS["ติดริมน้ำ"]["aspect"], "atmosphere")
        self.assertIn("canonical", lexicon.IDIOMS["ถึงเครื่อง"])

    def test_descriptor_hints(self):
        self.assertEqual(lexicon.DESCRIPTOR_ASPECT_HINTS["อร่อย"], "food")
        self.assertEqual(lexicon.DESCRIPTOR_ASPECT_HINTS["คึกคัก"], "atmosphere")

    def test_strip_sets(self):
        self.assertIn("มากๆ", lexicon.INTENSIFIERS)
        self.assertIn("คือ", lexicon.FILLERS)
        self.assertIn("แนะนำ", lexicon.META_VERBS)

    def test_synonym_groups_and_reverse(self):
        self.assertIn("ราคาไม่แพง", lexicon.SYNONYM_GROUPS["price_good"]["members"])
        key, label, aspect = lexicon.MEMBER_TO_CONCEPT["คุ้มค่า"]
        self.assertEqual((key, aspect), ("price_good", "food"))
        self.assertNotEqual(
            lexicon.MEMBER_TO_CONCEPT["ราคาแพง"][0],
            lexicon.MEMBER_TO_CONCEPT["ราคาไม่แพง"][0],
        )

    def test_distinct_descriptors_not_grouped(self):
        for w in ("อร่อย", "จัดจ้าน", "เข้มข้น", "ถึงเครื่อง"):
            self.assertNotIn(w, lexicon.MEMBER_TO_CONCEPT)


if __name__ == "__main__":
    unittest.main()
