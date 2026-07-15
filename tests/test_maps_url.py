"""ตรวจ URL ของ Google Maps ด้วย hostname จริง (urlparse) — substring เดิม
ปล่อย https://evil.com/?cid=1 ผ่าน ทำให้ยิง Apify เปลืองเครดิตได้"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app


class TestMapsUrlValidation(unittest.TestCase):
    def test_real_maps_urls_accepted(self):
        good = [
            "https://www.google.com/maps/place/xxx",
            "https://google.com/maps/place/xxx",
            "https://www.google.co.th/maps/place/xxx",
            "https://maps.google.com/?cid=123",
            "https://maps.google.co.th/abc",
            "https://goo.gl/maps/abc123",
            "https://maps.app.goo.gl/Juif524nahAVtqTt7",
            "https://www.google.com/?cid=12345",
        ]
        for url in good:
            self.assertTrue(app._looks_like_maps_url(url), url)

    def test_lookalike_urls_rejected(self):
        bad = [
            "https://evil.com/?cid=1",                       # cid บนโดเมนอื่น
            "https://evil.com/google.com/maps/place/x",       # โดเมนปลอมใน path
            "https://maps.google.com.evil.com/maps",          # subdomain หลอก
            "https://www.google.com/search?q=restaurant",     # google แต่ไม่ใช่ maps
            "javascript:alert(1)",
            "not a url",
            "",
        ]
        for url in bad:
            self.assertFalse(app._looks_like_maps_url(url), url)


if __name__ == "__main__":
    unittest.main()
