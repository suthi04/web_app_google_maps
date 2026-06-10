"""
tests/test_clause.py
====================
ทดสอบการแบ่งรีวิวเป็นอนุประโยค (clause) ตามคำเชื่อมแสดงความขัดแย้ง
เพื่อให้แต่ละอนุประโยคผูกอารมณ์กับหมวดของตัวเองได้ (aspect-level ที่ถูกต้อง)
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestSplitClauseTokens(unittest.TestCase):
    def test_splits_on_marker_token_only(self):
        from core.clause import split_clause_tokens
        toks = ["อาหาร", "อร่อย", "แต่", "บริการ", "ช้า"]
        self.assertEqual(
            split_clause_tokens(toks),
            [["อาหาร", "อร่อย"], ["บริการ", "ช้า"]],
        )

    def test_does_not_split_word_containing_marker(self):
        from core.clause import split_clause_tokens
        # "ตกแต่ง" is one token; must NOT be split even though it contains "แต่"
        toks = ["ร้าน", "ตกแต่ง", "สวย"]
        self.assertEqual(split_clause_tokens(toks), [["ร้าน", "ตกแต่ง", "สวย"]])

    def test_empty_returns_empty(self):
        from core.clause import split_clause_tokens
        self.assertEqual(split_clause_tokens([]), [])


if __name__ == "__main__":
    unittest.main()
