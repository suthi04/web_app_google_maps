import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import postag


class TestPostag(unittest.TestCase):
    def test_returns_pairs_for_each_token(self):
        out = postag.pos_tag(["อาหาร", "อร่อย"])
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0][0], "อาหาร")
        self.assertTrue(isinstance(out[0][1], str))

    def test_empty_input(self):
        self.assertEqual(postag.pos_tag([]), [])

    def test_available_is_bool(self):
        self.assertIn(postag.available(), (True, False))

    def test_tagsets_exist(self):
        self.assertIn("NOUN", postag.NOUN_TAGS)
        self.assertTrue(postag.STATIVE_TAGS)


if __name__ == "__main__":
    unittest.main()
