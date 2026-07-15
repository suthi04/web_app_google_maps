"""insights.py — aspect_summary นับเป็นราย "อนุประโยค/ความเห็น" (clause)
ข้อความที่แสดงต้องไม่เรียกตัวเลขนี้ว่า "รีวิว" (กันตัวเลขไม่ตรงกับจำนวนรีวิวจริง)"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import insights


def _summary(pos=0, neu=0, neg=0):
    return {"food": {"positive": pos, "neutral": neu, "negative": neg,
                     "total": pos + neu + neg}}


class TestInsightWording(unittest.TestCase):
    def test_insufficient_message_does_not_say_review(self):
        out = insights.generate_insights(_summary(pos=1), {})
        msg = out[0]["message"]
        self.assertEqual(out[0]["level"], "insufficient")
        self.assertNotIn("รีวิว", msg)        # นับ clause ไม่ใช่รีวิว — ห้ามเขียนว่ารีวิว
        self.assertIn("ความเห็น", msg)

    def test_thresholds_still_work(self):
        out = insights.generate_insights(_summary(pos=9, neg=1), {})
        self.assertEqual(out[0]["level"], "strength")
        out = insights.generate_insights(_summary(pos=2, neg=8), {})
        self.assertEqual(out[0]["level"], "improve")


if __name__ == "__main__":
    unittest.main()
