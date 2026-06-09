"""
keywords.py
===========
"ลูกค้าพูดถึงบ่อย" (Most Discussed Topics) — นับความถี่ของ "คำนามหัวหมวด"
ที่ลูกค้าเอ่ยถึง แยกตามหมวด (อาหาร/บริการ/บรรยากาศ) โดยไม่ผูกกับอารมณ์

หมายเหตุ: การสกัด "วลีคำสำคัญเชิงความเห็น" (opinion phrases) ย้ายไปอยู่ที่
core/phrases/ แล้ว (ดู core/pipeline.py:_phrase_pipeline) ไฟล์นี้จึงเหลือเฉพาะ
ส่วน "หัวข้อที่ถูกพูดถึงบ่อย" ซึ่งใช้เพื่อการสำรวจเท่านั้น — ไม่นำไปคำนวณ insight
หรือสรุปอารมณ์

คืน: {"food": [{"word","count"}...], "service": [...], "ambience": [...]}
"""
from collections import Counter

from core import lexicon
from core.lexicon import ASPECT_LEXICON

TOPICS_TOP_N = 8       # หัวข้อสูงสุดต่อหมวด
TOPICS_MIN_COUNT = 2   # ต้องถูกพูดถึงอย่างน้อยกี่ครั้งจึงนับว่า "บ่อย"

# ชื่อหมวดภายใน (food/service/atmosphere) -> คีย์ที่ dashboard ใช้ (food/service/ambience)
_ASPECT_KEY = {"food": "food", "service": "service", "atmosphere": "ambience"}


def _iter_clauses(reviews):
    """คืนอนุประโยคทั้งหมด (document = 1 อนุประโยค) — fallback เป็นทั้งรีวิวถ้าไม่มี clauses"""
    for r in reviews:
        clauses = r.get("clauses")
        if clauses:
            for c in clauses:
                yield c
        else:
            yield r


def extract_topics(reviews: list) -> dict:
    """นับ "คำนามหัวหมวด" (พนักงาน, แอร์, ที่จอดรถ ...) ที่ลูกค้าเอ่ยถึง แยกตามหมวด

    ใช้พจนานุกรมคำนามหัวหมวด (lexicon.NOUN_TO_ASPECT) เป็นแหล่งความจริงเดียว —
    คำบรรยายเชิงอารมณ์ (อร่อย/ดี) ไม่ใช่คำนามหัวหมวดจึงไม่ถูกนับเป็นหัวข้อ
    """
    counters = {a: Counter() for a in ASPECT_LEXICON}
    for c in _iter_clauses(reviews):
        for t in c.get("tokens_base", c.get("tokens", [])):
            a = _ASPECT_KEY.get(lexicon.NOUN_TO_ASPECT.get(t))
            if a in counters:
                counters[a][t] += 1

    result = {}
    for a, counter in counters.items():
        items = [(t, n) for t, n in counter.items() if n >= TOPICS_MIN_COUNT]
        items.sort(key=lambda x: x[1], reverse=True)
        result[a] = [{"word": t, "count": n} for t, n in items[:TOPICS_TOP_N]]
    return result
