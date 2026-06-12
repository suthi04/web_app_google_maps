"""
tests/test_aspect.py
====================
ทดสอบการจับหมวด (aspect) แบบ token-equality + substring แบบจำกัดความยาว (>=4)

เป้าหมาย:
- กำจัด false positive จากการ substring คำสั้น
  ("รอ"(บริการ) ไม่ควร match "กรอบ"; "เย็น"(บรรยากาศ) ไม่ควร match "เย็นชืด")
- คงการจับคำประสมยาว ๆ ที่ตัวตัดคำรวมกัน
  ("พนักงานบริการ" ต้องยังนับเป็นบริการ ผ่านคำว่า "บริการ"(6 ตัว))
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import aspect


def detect(tokens_base):
    return set(aspect.detect_aspects({"tokens_base": tokens_base}))


class TestAspectDetection(unittest.TestCase):
    def test_exact_token_match(self):
        self.assertEqual(detect(["บริการ", "ช้า"]), {"service"})

    def test_crispy_food_not_tagged_service(self):
        # "เนื้อกรอบ" -> ["เนื้อ","กรอบ"] : "รอ"(2 ตัว) ต้องไม่ match "กรอบ"
        result = detect(["เนื้อ", "กรอบ"])
        self.assertNotIn("service", result)
        self.assertIn("food", result)  # "เนื้อ" อยู่ในหมวดอาหาร

    def test_cold_stale_food_not_tagged_ambience(self):
        # "อาหารเย็นชืด" -> ["อาหาร","เย็นชืด"] : "เย็น"(3 ตัว) ต้องไม่ match "เย็นชืด"
        result = detect(["อาหาร", "เย็นชืด"])
        self.assertNotIn("ambience", result)
        self.assertIn("food", result)

    def test_long_compound_still_matches_service(self):
        # ตัวตัดคำรวม "พนักงานบริการ" : คำยาว ("บริการ" 6 ตัว) ต้องยัง match แบบ substring
        self.assertEqual(detect(["พนักงานบริการ", "ดี"]), {"service"})

    def test_multiword_aspect_noun_exact(self):
        self.assertEqual(detect(["ที่จอดรถ", "น้อย"]), {"ambience"})

    def test_uncategorized(self):
        self.assertEqual(detect(["เปิด", "สาม", "ทุ่ม"]), set())

    def test_tag_aspects_sets_uncategorized(self):
        reviews = [{"tokens_base": ["เปิด", "สาม", "ทุ่ม"]}]
        out = aspect.tag_aspects(reviews)
        self.assertEqual(out[0]["aspects"], ["uncategorized"])


if __name__ == "__main__":
    unittest.main()
