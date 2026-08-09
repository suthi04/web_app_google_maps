"""Fast structural checks for the accessibility contract in server markup."""

import os
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app


ROOT = Path(__file__).resolve().parents[1]


class TestAccessibilityMarkup(unittest.TestCase):
    def test_base_page_has_skip_target_live_regions_and_current_page(self):
        html = app.app.test_client().get("/").get_data(as_text=True)
        self.assertIn('href="#mainContent"', html)
        self.assertIn('id="mainContent"', html)
        self.assertIn('aria-live="polite"', html)
        self.assertIn('aria-current="page"', html)

    def test_analysis_form_has_duplicate_submit_guard_and_url_bound(self):
        html = app.app.test_client().get("/").get_data(as_text=True)
        self.assertIn("data-guard-submit", html)
        self.assertIn('maxlength="2048"', html)
        self.assertIn('aria-label="ลิงก์ร้านอาหารจาก Google Maps"', html)
        self.assertIn('name="engine"', html)
        self.assertIn('name="extract_engine"', html)
        self.assertIn('name="max_reviews"', html)

    def test_template_buttons_declare_type_and_history_has_real_link(self):
        templates = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / "templates").glob("*.html")
        )
        missing_type = re.findall(r"<button(?![^>]*\btype=)[^>]*>", templates)
        self.assertEqual(missing_type, [])
        history = (ROOT / "templates" / "history.html").read_text(encoding="utf-8")
        self.assertIn('<a class="hist-main" href=', history)
        self.assertNotIn("onclick=", history)


if __name__ == "__main__":
    unittest.main()
