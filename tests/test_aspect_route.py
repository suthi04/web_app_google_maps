import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.phrases.model import Phrase
from core import aspect


class TestRouteAspect(unittest.TestCase):
    def test_tier1_idiom(self):
        p = Phrase(surface="ติดริมน้ำ", pattern="idiom")
        self.assertEqual(aspect.route_aspect(p, [])[0], "atmosphere")

    def test_tier1_synonym_concept(self):
        p = Phrase(surface="คุ้มค่า", canonical="คุ้มค่า", concept="price_good")
        self.assertEqual(aspect.route_aspect(p, [])[0], "food")

    def test_tier2_head_noun(self):
        p = Phrase(surface="ราคา ไม่ แพง", head_noun="ราคา",
                   descriptor_tokens=["ไม่", "แพง"], concept="x")
        self.assertEqual(aspect.route_aspect(p, ["service"])[0], "food")

    def test_tier3_single_clause_aspect(self):
        p = Phrase(surface="หยาบคาย", descriptor_tokens=["หยาบคาย"], concept="x")
        self.assertEqual(aspect.route_aspect(p, ["service"])[0], "service")

    def test_tier4_descriptor_hint(self):
        p = Phrase(surface="คึกคัก", descriptor_tokens=["คึกคัก"], concept="x")
        self.assertEqual(aspect.route_aspect(p, ["food", "service"])[0], "atmosphere")

    def test_uncategorized(self):
        p = Phrase(surface="งง", descriptor_tokens=["งง"], concept="x")
        self.assertEqual(aspect.route_aspect(p, ["food", "service"])[0], None)

    def test_detect_clause_aspects(self):
        clause = {"raw_tokens": ["พนักงาน", "ใจดี"], "tokens_base": ["พนักงาน", "ใจดี"]}
        self.assertIn("service", aspect.detect_clause_aspects(clause))


if __name__ == "__main__":
    unittest.main()
