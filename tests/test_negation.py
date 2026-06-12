"""
tests/test_negation.py
======================
ทดสอบการรวมคำปฏิเสธกับคำแสดงอารมณ์ (negation handling)

หลักการที่ทดสอบ:
- "ไม่ อร่อย" -> "ไม่อร่อย" (รวมเป็นหน่วยเดียว เพื่อไม่ให้ "อร่อย" หลุดเป็นคำบวก)
- รวมเฉพาะเมื่อคำถัดไปเป็นคำขั้ว (polar) เท่านั้น กันการรวมมั่ว เช่น "ไม่ ร้าน"
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import negation


class TestNegation(unittest.TestCase):
    def test_merges_negator_with_following_positive_word(self):
        # "ไม่" + "อร่อย" ต้องกลายเป็น "ไม่อร่อย" หน่วยเดียว
        self.assertEqual(
            negation.apply_negation(["อาหาร", "ไม่", "อร่อย", "เลย"]),
            ["อาหาร", "ไม่อร่อย", "เลย"],
        )

    def test_merges_degree_negator_kept_whole_by_tokenizer(self):
        # newmm คืน "ไม่ค่อย" เป็นโทเคนเดียว -> ต้องรวมกับคำขั้วถัดไปได้
        self.assertEqual(
            negation.apply_negation(["ไม่ค่อย", "อร่อย"]),
            ["ไม่ค่อยอร่อย"],
        )

    def test_merges_with_aspect_polarity_word(self):
        # "เย็น" (แอร์เย็น) เป็นคำขั้วเชิงบรรยากาศ -> "ไม่เย็น" ต้องรวม
        self.assertEqual(
            negation.apply_negation(["แอร์", "ไม่", "เย็น"]),
            ["แอร์", "ไม่เย็น"],
        )

    def test_does_not_merge_with_nonpolar_word(self):
        # "ไม่" + "ร้าน" ไม่ใช่คำขั้ว -> ห้ามรวม (กันสร้างคำขยะ)
        self.assertEqual(
            negation.apply_negation(["ไม่", "ร้าน"]),
            ["ไม่", "ร้าน"],
        )

    def test_negator_at_end_is_left_untouched(self):
        self.assertEqual(
            negation.apply_negation(["อร่อย", "ไม่"]),
            ["อร่อย", "ไม่"],
        )

    def test_no_negator_returns_same_tokens(self):
        self.assertEqual(
            negation.apply_negation(["อาหาร", "อร่อย", "มาก"]),
            ["อาหาร", "อร่อย", "มาก"],
        )

    def test_empty(self):
        self.assertEqual(negation.apply_negation([]), [])


if __name__ == "__main__":
    unittest.main()
