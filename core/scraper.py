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

import requests

import config

# Endpoint แบบ "run แล้วรอผลในครั้งเดียว" ของ Apify
# รูปแบบ: POST /v2/acts/{actor}/run-sync-get-dataset-items?token=...
APIFY_ENDPOINT = (
    "https://api.apify.com/v2/acts/"
    "compass~google-maps-reviews-scraper/run-sync-get-dataset-items"
)


def _fetch_from_apify(url: str, max_reviews: int) -> dict:
    """เรียก Apify จริง — ต้องมี APIFY_TOKEN และอินเทอร์เน็ต"""
    # NOTE: ชื่อฟิลด์ input ขึ้นกับ actor แต่ละตัว ตรวจได้ที่หน้า actor บน Apify (แท็บ Input)
    #       ด้านล่างเป็นค่าที่ใช้ได้กับ compass/google-maps-reviews-scraper
    payload = {
        "startUrls": [{"url": url}],
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
    except requests.RequestException as e:
        raise RuntimeError(f"เชื่อมต่อ Apify ไม่ได้: {e}")

    if resp.status_code >= 300:
        # 401=token ผิด, 402=เครดิตหมด, 400=input ผิด, 408=timeout ฝั่ง Apify
        raise RuntimeError(f"Apify ตอบกลับ error {resp.status_code}: {resp.text[:200]}")

    items = resp.json()

    reviews = []
    store_name = None
    for it in items:
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

    if config.get_apify_token():
        return _fetch_from_apify(url, max_reviews)
    return _fetch_from_sample(url, max_reviews)