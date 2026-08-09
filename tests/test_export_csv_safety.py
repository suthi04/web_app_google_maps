"""CSV formula injection: ข้อความรีวิว (คนเขียนรีวิวควบคุมได้) ที่ขึ้นต้นด้วย
= + - @ ต้องถูก escape ด้วย apostrophe กัน Excel ตีความเป็นสูตร"""
import csv
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import export


def _analysis(text="อร่อยมาก", store="ครัวบ้านสวน"):
    return {
        "store_name": store,
        "total_reviews": 1,
        "engine": "lexicon",
        "distribution": {"pct": {}, "counts": {}},
        "aspect_summary": {},
        "insights": [],
        "reviews": [{"text": text, "rating": 5, "review_date": "2026-01-01",
                     "sentiment": "positive", "aspects": ["food"]}],
    }


class TestCsvFormulaInjection(unittest.TestCase):
    def test_formula_prefixes_are_escaped_in_reviews_csv(self):
        for evil in (
            "=HYPERLINK(\"http://evil\")", "+1+1", "-2+3", "@SUM(A1)",
            "  =SUM(A1)", "\t=SUM(A1)",
        ):
            with self.subTest(value=evil):
                csv_text = export.reviews_csv(_analysis(text=evil))
                rows = list(csv.reader(io.StringIO(csv_text.lstrip("\ufeff"))))
                self.assertEqual(rows[1][1], "'" + evil)

    def test_normal_thai_text_untouched(self):
        csv_text = export.reviews_csv(_analysis(text="อร่อยมาก"))
        self.assertIn("อร่อยมาก", csv_text)
        self.assertNotIn("'อร่อยมาก", csv_text)

    def test_review_export_uses_stable_reference_id(self):
        csv_text = export.reviews_csv(_analysis())
        rows = list(csv.reader(io.StringIO(csv_text.lstrip("\ufeff"))))
        self.assertEqual(rows[0][0], "รหัสอ้างอิง")
        self.assertEqual(rows[1][0], "R001")

    def test_store_name_escaped_in_summary_csv(self):
        csv_text = export.summary_csv(_analysis(store="=cmd()"))
        self.assertIn("'=cmd()", csv_text)


if __name__ == "__main__":
    unittest.main()
