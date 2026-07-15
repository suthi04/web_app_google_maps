import os
import sys
import unittest
from unittest import mock

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from core import scraper


def _response(payload=None, error=None):
    response = mock.Mock()
    response.status_code = 200
    response.text = ""
    if error is not None:
        response.json.side_effect = error
    else:
        response.json.return_value = payload
    return response


class TestApifyResponseBoundaries(unittest.TestCase):
    @mock.patch.object(config, "get_apify_token", return_value="token")
    def test_non_json_response_has_clear_runtime_error(self, _token):
        error = requests.JSONDecodeError("bad json", "x", 0)
        with mock.patch.object(scraper.requests, "post", return_value=_response(error=error)):
            with self.assertRaisesRegex(RuntimeError, "JSON"):
                scraper._fetch_from_apify("https://maps.google.com/maps", 10)

    @mock.patch.object(config, "get_apify_token", return_value="token")
    def test_non_list_payload_is_rejected(self, _token):
        with mock.patch.object(scraper.requests, "post", return_value=_response({"x": 1})):
            with self.assertRaisesRegex(RuntimeError, "รูปแบบ"):
                scraper._fetch_from_apify("https://maps.google.com/maps", 10)

    @mock.patch.object(config, "get_apify_token", return_value="token")
    def test_invalid_items_are_skipped(self, _token):
        payload = [None, "bad", {"text": "อร่อย", "title": "ร้านดี", "stars": 5}]
        with mock.patch.object(scraper.requests, "post", return_value=_response(payload)):
            result = scraper._fetch_from_apify("https://maps.google.com/maps", 10)
        self.assertEqual(result["store_name"], "ร้านดี")
        self.assertEqual(len(result["reviews"]), 1)

    def test_requested_review_count_is_bounded(self):
        with (
            mock.patch.object(config, "get_apify_token", return_value=""),
            mock.patch.object(scraper, "_fetch_from_sample", return_value={}) as fetch,
        ):
            scraper.fetch_reviews("", config.MAX_REVIEWS_CAP + 999)
        fetch.assert_called_once_with("", config.MAX_REVIEWS_CAP)


if __name__ == "__main__":
    unittest.main()
