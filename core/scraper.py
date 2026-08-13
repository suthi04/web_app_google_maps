"""
scraper.py
==========
ดึงรีวิวร้านอาหารจาก Google Maps

มี 2 โหมด ควบคุมที่ config.py:
- โหมดจริง  (APIFY_TOKEN ถูกตั้งค่า) -> เรียก Apify actor "compass/google-maps-reviews-scraper"
- โหมด demo (APIFY_TOKEN ว่าง)       -> โหลดรีวิวตัวอย่างจาก data/sample_reviews.json
                                        ทำให้รันได้ทันทีโดยไม่ต้องมี token

ฟังก์ชันหลัก: fetch_reviews(url, max_reviews) -> dict
    {
      "store_name": str,
      "source_url": str,
      "reviews": [ {"text": str, "rating": int|None, "review_date": str|None}, ... ]
    }
"""
import json
import os
from urllib.parse import parse_qs, urlparse

import requests

import config

# Endpoint แบบ "run แล้วรอผลในครั้งเดียว" ของ Apify
# รูปแบบ: POST /v2/acts/{actor}/run-sync-get-dataset-items?token=...
APIFY_ENDPOINT = (
    "https://api.apify.com/v2/acts/"
    "compass~google-maps-reviews-scraper/run-sync-get-dataset-items"
)

_SHORT_MAPS_HOSTS = {"maps.app.goo.gl", "goo.gl"}


def _is_direct_google_maps_url(url: str) -> bool:
    """Accept only direct Google Maps destinations supported by the Actor."""
    try:
        parsed = urlparse((url or "").strip())
    except ValueError:
        return False
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    host = parsed.hostname.lower().rstrip(".")
    path = parsed.path.lower()
    is_google = (
        host in {"google.com", "google.co.th"}
        or host.endswith(".google.com")
        or host.endswith(".google.co.th")
    )
    if not is_google:
        return False
    return (
        path == "/maps"
        or path.startswith(("/maps/", "/maps/place", "/maps/search", "/maps/reviews"))
        or "cid" in parse_qs(parsed.query, keep_blank_values=True)
    )


def _resolve_maps_url(url: str) -> str:
    """Expand Google Maps short links before passing them to Apify.

    The reviews Actor validates direct place URLs and can reject ``maps.app.goo.gl``
    links before a run is created.  Follow redirects without downloading the page
    body, then fail closed unless the destination is still an HTTPS Google Maps URL.
    """
    original = (url or "").strip()
    try:
        parsed = urlparse(original)
    except ValueError:
        raise RuntimeError("ลิงก์ Google Maps ไม่ถูกต้อง กรุณาคัดลอกลิงก์ใหม่") from None
    host = (parsed.hostname or "").lower().rstrip(".")
    if host not in _SHORT_MAPS_HOSTS:
        return original

    response = None
    try:
        response = requests.get(
            original,
            allow_redirects=True,
            stream=True,
            timeout=min(config.APIFY_TIMEOUT, 20),
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        resolved = response.url
    except requests.RequestException:
        raise RuntimeError(
            "เปิดลิงก์ Google Maps แบบย่อไม่ได้ กรุณาลองคัดลอกลิงก์จาก Google Maps ใหม่"
        ) from None
    finally:
        if response is not None:
            response.close()

    if not _is_direct_google_maps_url(resolved):
        raise RuntimeError(
            "ลิงก์แบบย่อไม่ได้ชี้ไปยังหน้าร้านบน Google Maps กรุณาตรวจสอบลิงก์"
        )
    return resolved


def _fetch_from_apify(url: str, max_reviews: int) -> dict:
    """เรียก Apify จริง — ต้องมี APIFY_TOKEN และอินเทอร์เน็ต"""
    # NOTE: ชื่อฟิลด์ input ขึ้นกับ actor แต่ละตัว ตรวจได้ที่หน้า actor บน Apify (แท็บ Input)
    #       ด้านล่างเป็นค่าที่ใช้ได้กับ compass/google-maps-reviews-scraper
    resolved_url = _resolve_maps_url(url)
    payload = {
        "startUrls": [{"url": resolved_url}],
        "maxReviews": max_reviews,
        "reviewsSort": "newest",   # newest | mostRelevant | highestRanking | lowestRanking
        "language": "th",
    }
    try:
        resp = requests.post(
            APIFY_ENDPOINT,
            params={"token": config.get_apify_token()},
            json=payload,
            timeout=config.APIFY_TIMEOUT,
        )
    except requests.Timeout:
        raise RuntimeError(
            f"Apify ใช้เวลานานเกิน {config.APIFY_TIMEOUT} วินาที (timeout) "
            f"ลองลด MAX_REVIEWS หรือเพิ่ม APIFY_TIMEOUT"
        )
    except requests.RequestException:
        # requests includes the full request URL in its exception string; that URL
        # contains the Apify token query parameter. Do not let it reach app logs.
        raise RuntimeError(
            "เชื่อมต่อ Apify ไม่ได้ กรุณาตรวจสอบอินเทอร์เน็ตแล้วลองใหม่"
        ) from None

    if resp.status_code >= 300:
        # 401=token ผิด, 402=เครดิตหมด, 400=input ผิด, 408=timeout ฝั่ง Apify
        raise RuntimeError(f"Apify ตอบกลับ error {resp.status_code}")

    try:
        items = resp.json()
    except requests.JSONDecodeError as e:
        raise RuntimeError("Apify ตอบกลับมาเป็นข้อมูลที่ไม่ใช่ JSON") from e
    if not isinstance(items, list):
        raise RuntimeError("Apify ตอบกลับมาในรูปแบบที่ไม่ถูกต้อง (ต้องเป็นรายการรีวิว)")

    reviews = []
    store_name = None
    for it in items:
        if not isinstance(it, dict):
            continue
        # field ที่ actor คืนมา (ปรับชื่อ key ให้ตรง actor จริงได้)
        text = it.get("text") or it.get("reviewText") or ""
        if not text.strip():
            continue
        if store_name is None:
            store_name = it.get("title") or it.get("placeName")
        reviews.append({
            "text": text.strip(),
            "rating": it.get("stars") or it.get("rating"),
            "review_date": it.get("publishedAtDate") or it.get("publishAt"),
        })

    return {
        "store_name": store_name or "ร้านอาหาร",
        "source_url": url,
        "reviews": reviews,
    }


def _fetch_from_sample(url: str, max_reviews: int) -> dict:
    """โหมด demo — โหลดข้อมูลตัวอย่าง"""
    path = os.path.join(config.DATA_DIR, "sample_reviews.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    data["source_url"] = url or data.get("source_url", "")
    data["reviews"] = data["reviews"][:max_reviews]
    return data


def fetch_reviews(url: str, max_reviews: int = None) -> dict:
    """
    ดึงรีวิว — เลือกโหมดอัตโนมัติจาก config
    """
    if max_reviews is None:
        max_reviews = config.get_max_reviews()
    try:
        max_reviews = int(max_reviews)
    except (TypeError, ValueError, OverflowError):
        max_reviews = config.get_max_reviews()
    max_reviews = max(1, min(config.MAX_REVIEWS_CAP, max_reviews))

    if config.get_apify_token():
        return _fetch_from_apify(url, max_reviews)
    return _fetch_from_sample(url, max_reviews)
