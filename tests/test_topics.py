"""
tests/test_topics.py
====================
ทดสอบส่วน "ลูกค้าพูดถึงบ่อย" (Most Discussed Topics)

ข้อกำหนดสำคัญ:
- topics ใช้เฉพาะ "คำนามหัวหมวด" (หัวข้อที่พูดถึง) ไม่เกี่ยวกับอารมณ์
- ต้อง "แยกขาด" จากคำสำคัญเชิงความเห็น และห้ามมีผลต่อ insight/สรุปอารมณ์
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import keywords


def _words(bucket):
    return [k["word"] for k in bucket]


class TestTopics(unittest.TestCase):
    def test_topics_collects_aspect_nouns(self):
        reviews = [{
            "clauses": [
                {"tokens": ["พนักงาน", "ดี"], "tokens_base": ["พนักงาน", "ดี"],
                 "aspects": ["service"], "sentiment": "positive"},
                {"tokens": ["พนักงาน", "ช้า"], "tokens_base": ["พนักงาน", "ช้า"],
                 "aspects": ["service"], "sentiment": "negative"},
            ],
        }]
        topics = keywords.extract_topics(reviews)
        self.assertIn("พนักงาน", _words(topics["service"]))

    def test_topics_exclude_opinion_words(self):
        reviews = [{
            "clauses": [
                {"tokens": ["อร่อย"], "tokens_base": ["อร่อย"],
                 "aspects": ["food"], "sentiment": "positive"},
            ],
        }]
        topics = keywords.extract_topics(reviews)
        # "อร่อย" เป็นคำบรรยาย ไม่ใช่หัวข้อ -> ต้องไม่อยู่ใน topics
        self.assertNotIn("อร่อย", _words(topics["food"]))

    def test_topics_shape(self):
        topics = keywords.extract_topics([])
        self.assertEqual(set(topics.keys()), {"food", "service", "ambience"})
        for lst in topics.values():
            self.assertIsInstance(lst, list)


if __name__ == "__main__":
    unittest.main()
