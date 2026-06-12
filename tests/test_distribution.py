"""
tests/test_distribution.py
==========================
ผลรวมเปอร์เซ็นต์ของ distribution ต้องเป็น 100 เสมอเมื่อมีรีวิว
(กันบั๊กการปัดเศษแยกค่าที่อาจให้ผลรวม 99/101 เช่น 33+33+33)
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import pipeline


def _reviews(pos, neu, neg):
    out = []
    for sent, n in (("positive", pos), ("neutral", neu), ("negative", neg)):
        out += [{"sentiment": sent} for _ in range(n)]
    return out


class TestDistributionPercent(unittest.TestCase):
    def test_pct_always_sums_to_100(self):
        # รวม combo ที่ round() แยกค่าจะเพี้ยน (1/1/1 -> 33+33+33=99)
        for combo in [(1, 1, 1), (2, 1, 1), (7, 2, 1), (1, 1, 4),
                      (0, 0, 3), (5, 5, 5), (1, 2, 0), (10, 10, 10)]:
            dist = pipeline._sentiment_distribution(_reviews(*combo))
            self.assertEqual(sum(dist["pct"].values()), 100, combo)

    def test_zero_reviews_is_all_zero(self):
        dist = pipeline._sentiment_distribution([])
        self.assertEqual(dist["pct"], {"positive": 0, "neutral": 0, "negative": 0})
        self.assertEqual(dist["total"], 0)

    def test_counts_and_total_preserved(self):
        dist = pipeline._sentiment_distribution(_reviews(3, 2, 1))
        self.assertEqual(dist["counts"], {"positive": 3, "neutral": 2, "negative": 1})
        self.assertEqual(dist["total"], 6)

    def test_remainder_goes_to_largest_fraction(self):
        # 1 pos / 2 neu / 0 neg = 33.33 / 66.67 / 0 -> เศษไปที่ neutral -> 33/67/0
        dist = pipeline._sentiment_distribution(_reviews(1, 2, 0))
        self.assertEqual(dist["pct"], {"positive": 33, "neutral": 67, "negative": 0})


if __name__ == "__main__":
    unittest.main()
