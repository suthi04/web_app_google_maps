"""
tests/test_sentiment_negation.py
================================
ทดสอบว่า engine แบบ lexicon ตีความคำปฏิเสธถูกต้อง เมื่อรับโทเคนที่ผ่านการรวม
negation มาแล้ว (จาก core/negation.apply_negation)

โฟกัส: คำปฏิเสธต้อง "พลิกขั้ว" ไม่ใช่ปล่อยให้ substring fallback นับ "สะอาด" ใน
"ไม่สะอาด" เป็นบวก
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import sentiment


def s(tokens):
    return sentiment._predict_lexicon(tokens)


class TestLexiconNegation(unittest.TestCase):
    def test_plain_positive(self):
        self.assertEqual(s(["อาหาร", "อร่อย", "มาก"]), "positive")

    def test_plain_negative(self):
        self.assertEqual(s(["บริการ", "ช้า"]), "negative")

    def test_merged_negation_in_lexicon(self):
        # "ไม่อร่อย" มีใน lexicon ลบอยู่แล้ว -> ต้องเป็นลบ ไม่ใช่บวกจาก "อร่อย"
        self.assertEqual(s(["อาหาร", "ไม่อร่อย", "เลย"]), "negative")

    def test_merged_negation_not_in_lexicon_flips_positive_base(self):
        # "ไม่สะอาด" ไม่มีใน lexicon แต่ฐาน "สะอาด" เป็นบวก -> ต้องพลิกเป็นลบ
        self.assertEqual(s(["ไม่สะอาด"]), "negative")

    def test_merged_negation_flips_chop(self):
        # "ไม่ชอบ" -> ลบ
        self.assertEqual(s(["ไม่ชอบ"]), "negative")

    def test_neutral_when_no_polarity(self):
        self.assertEqual(s(["ร้าน", "เปิด", "สาม", "ทุ่ม"]), "neutral")


if __name__ == "__main__":
    unittest.main()
