"""
aspect.py
=========
จัดหมวดรีวิวเป็น อาหาร / บริการ / บรรยากาศ ด้วยวิธีพจนานุกรมคำสำคัญ (Lexicon-based)

หลักการ:
- ตรวจว่ารีวิวมีคำที่ตรงกับพจนานุกรมหมวดใดบ้าง (รีวิวเดียวอยู่ได้หลายหมวด)
- ผูกอารมณ์ของรีวิว (จาก sentiment.py) เข้ากับหมวดที่พบ
- รีวิวที่ไม่เข้าหมวดใดเลย -> "uncategorized"

ฟังก์ชันหลัก: tag_aspects(reviews) -> ใส่ key 'aspects' (list) ให้แต่ละรีวิว
"""
from core.lexicon import ASPECT_LEXICON


def detect_aspects(review: dict) -> list:
    """
    คืนรายการหมวดที่รีวิวนี้กล่าวถึง เช่น ["food", "service"]
    เช็คทั้งจาก tokens และแบบ substring กับข้อความรวม (กันคำไม่ถูกตัด)
    """
    tokens = set(review.get("tokens", []))
    joined = review.get("clean", "") or "".join(review.get("tokens", []))
    found = []
    for aspect, words in ASPECT_LEXICON.items():
        hit = any(w in tokens for w in words) or any(w in joined for w in words)
        if hit:
            found.append(aspect)
    return found


def tag_aspects(reviews: list) -> list:
    """ใส่ key 'aspects' ให้รีวิวทุกรายการ"""
    for r in reviews:
        aspects = detect_aspects(r)
        r["aspects"] = aspects if aspects else ["uncategorized"]
    return reviews


def aspect_sentiment_summary(reviews: list) -> dict:
    """
    สรุปจำนวนอารมณ์ราย aspect
    คืน: {
      "food":    {"positive": n, "neutral": n, "negative": n, "total": n},
      "service": {...}, "ambience": {...}
    }
    (ไม่รวม uncategorized ในสรุปหลัก)
    """
    summary = {
        a: {"positive": 0, "neutral": 0, "negative": 0, "total": 0}
        for a in ASPECT_LEXICON
    }
    for r in reviews:
        sent = r.get("sentiment", "neutral")
        for a in r.get("aspects", []):
            if a in summary:
                summary[a][sent] += 1
                summary[a]["total"] += 1
    return summary
