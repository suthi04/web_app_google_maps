import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.phrases import extract


class TestPublicExtract(unittest.TestCase):
    def _clause(self, raw):
        return {"raw_tokens": raw, "tokens": raw, "tokens_base": raw, "clean": "".join(raw)}

    def test_noun_descriptor_phrase(self):
        out = extract.extract(self._clause(["อาหาร", "อร่อย"]))
        self.assertTrue(any(p.head_noun == "อาหาร" and "อร่อย" in p.descriptor_tokens
                            for p in out))

    def test_idiom_priority(self):
        out = extract.extract(self._clause(["ติด", "ริมน้ำ"]))
        self.assertTrue(any(p.pattern == "idiom" and p.surface == "ติดริมน้ำ" for p in out))

    def test_descriptor_compound_via_public(self):
        out = extract.extract(self._clause(["เย็น", "สบาย"]))
        self.assertTrue(any(p.surface == "เย็นสบาย" and p.aspect == "atmosphere" for p in out))

    def test_empty_clause(self):
        self.assertEqual(extract.extract({"raw_tokens": []}), [])
