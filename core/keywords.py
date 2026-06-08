"""
keywords.py
===========
สกัดคำสำคัญ (keyword) ของร้าน แยกตามหมวด (aspect) และอารมณ์ (sentiment)

ปัญหาเดิม (แก้แล้ว):
    รีวิว 1 รายการที่พูดถึงหลายหมวด (เช่น "อาหารอร่อยแต่บริการช้า") เคยเอา token
    ทั้งหมดยัดเข้า "ทุกหมวด" ที่รีวิวนั้นแตะ -> คำว่า "บริการ" ไปโผล่ในหมวดอาหาร,
    คำว่า "อร่อย" ไปโผล่ในบริการ = แยกมั่ว

วิธีใหม่ (lexicon attribution):
    แบ่ง token เข้าหมวดตามความหมายของตัวคำเอง ไม่ใช่ตามรีวิว
      1) ถ้า token เป็นคำเฉพาะหมวด (อยู่ในพจนานุกรม ASPECT_LEXICON)
         -> เข้าเฉพาะหมวดของมันเท่านั้น  (พนักงาน->บริการ, แอร์->บรรยากาศ)
      2) ถ้า token เป็นคำกลาง/คำอารมณ์ (อร่อย, แย่, แพง — ไม่ผูกหมวด)
         -> ใส่ให้ก็ต่อเมื่อรีวิวนั้นพูดถึง "หมวดเดียว" (ไม่กำกวม)
            ถ้ารีวิวพูดหลายหมวด = ข้าม (กันปนข้ามหมวด)

จัดอันดับด้วย TF-IDF (score = ความถี่ x idf) เพื่อดึงคำเด่นเฉพาะร้าน
ไม่พึ่ง sklearn (คำนวณเองด้วย math.log)

ฟังก์ชันหลัก: extract_keywords(reviews) -> dict ซ้อน aspect -> sentiment -> [keywords]
"""
import math
from collections import Counter

from core.lexicon import ASPECT_LEXICON

# คำทั่วไป/คำหน้าที่ ที่ไม่มีความหมายพอจะเป็น keyword (เสริมจาก stopword ของ PyThaiNLP)
_IGNORE = {
    "ร้าน", "มาก", "ไป", "เลย", "นะ", "ค่ะ", "ครับ", "จ้า", "ๆ", "และ", "ที่",
    "มี", "ของ", "เป็น", "ก็", "อยู่", "มา", "แบบ", "คือ", "ได้", "ให้", "กับ",
    "อันนี้", "อะ", "ด้วย", "แต่", "หน่อย", "นี้", "นั้น", "เรา", "เขา", "ทาน",
    "กิน", "ค่อนข้าง", "นิด", "พอ", "จะ", "ไม่", "ว่า", "ถ้า", "ตอน",
    # คำขยะที่เคยหลุดมาเป็น keyword
    "ทำ", "หน้า", "รอบ", "แทบ", "ได้ยิน", "หา", "ติด", "พอใจ", "กลางๆ",
    "สั่งอาหาร", "สั่ง", "ทักท้วง", "เฉยๆ", "อีก", "ขึ้น", "ลง", "ใช้", "ครั้ง",
    "หลาย", "เยอะ", "น้อย", "ทุก", "บาง", "เคย", "ยัง", "แล้ว", "เอา", "เห็น",
}

MIN_LEN = 2          # คำต้องยาวอย่างน้อยกี่ตัวอักษร
TOP_N = 8            # เก็บกี่ keyword ต่อกลุ่ม

# reverse map: token -> เซ็ตของหมวดที่คำนั้นสังกัด (สร้างจากพจนานุกรม)
_TOKEN_ASPECT = {}
for _asp, _words in ASPECT_LEXICON.items():
    for _w in _words:
        _TOKEN_ASPECT.setdefault(_w, set()).add(_asp)


def _is_good_token(tok: str) -> bool:
    return len(tok) >= MIN_LEN and tok not in _IGNORE and not tok.isnumeric()


def _compute_idf(reviews: list) -> dict:
    """idf จากคลังรีวิวของร้านนี้ (document = 1 รีวิว)"""
    n = len(reviews) or 1
    df = Counter()
    for r in reviews:
        seen = {t for t in r.get("tokens", []) if _is_good_token(t)}
        df.update(seen)
    return {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}


def extract_keywords(reviews: list) -> dict:
    """
    คืนโครงสร้าง:
    {
      "food":    {"positive": [...], "neutral": [...], "negative": [...]},
      "service": {...},
      "ambience":{...}
    }
    แต่ละ list = [{"word": str, "count": int}, ...] เรียงตามคะแนน TF-IDF จากมากไปน้อย
    """
    idf = _compute_idf(reviews)
    aspects = set(ASPECT_LEXICON.keys())
    buckets = {
        a: {"positive": Counter(), "neutral": Counter(), "negative": Counter()}
        for a in ASPECT_LEXICON
    }

    for r in reviews:
        sent = r.get("sentiment", "neutral")
        review_aspects = [a for a in r.get("aspects", []) if a in aspects]
        if not review_aspects:
            continue
        single = review_aspects[0] if len(review_aspects) == 1 else None

        for t in r.get("tokens", []):
            if not _is_good_token(t):
                continue
            own = _TOKEN_ASPECT.get(t, set()) & aspects
            if own:
                # คำเฉพาะหมวด -> เข้าเฉพาะหมวดของมัน (ที่รีวิวนี้พูดถึง)
                for a in own:
                    if a in review_aspects:
                        buckets[a][sent][t] += 1
            elif single:
                # คำกลาง/คำอารมณ์ -> ใส่ได้เฉพาะเมื่อรีวิวพูดถึงหมวดเดียว (ไม่กำกวม)
                buckets[single][sent][t] += 1
            # else: คำกลางในรีวิวหลายหมวด -> ข้าม (กันปนข้ามหมวด)

    result = {}
    for a, by_sent in buckets.items():
        result[a] = {}
        for sent, counter in by_sent.items():
            scored = [
                (word, count, count * idf.get(word, 1.0))
                for word, count in counter.items()
            ]
            scored.sort(key=lambda x: (x[2], x[1]), reverse=True)
            result[a][sent] = [{"word": w, "count": c} for w, c, _ in scored[:TOP_N]]
    return result
