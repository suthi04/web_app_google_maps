"""Landing page structure and analysis controls."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app


class TestHomeRoute(unittest.TestCase):
    def test_renders_redesigned_analysis_composer(self):
        html = app.app.test_client().get("/").get_data(as_text=True)

        self.assertIn('class="landing-copy"', html)
        self.assertIn('class="composer-topline"', html)
        self.assertEqual(html.count('<details class="landing-picker'), 3)
        self.assertIn('class="landing-benefits"', html)
        self.assertIn('class="btn btn-primary btn-pill analyze-btn"', html)
        self.assertEqual(html.count("data-select-display"), 3)
        self.assertIn('class="landing-picker-menu"', html)
        self.assertIn('class="landing-picker-choice"', html)
        self.assertIn("วิเคราะห์อารมณ์", html)
        self.assertIn("สกัดประเด็น", html)
        self.assertIn("ตรวจสอบจากรีวิวจริง", html)


if __name__ == "__main__":
    unittest.main()
