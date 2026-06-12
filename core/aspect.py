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
from core import lexicon  # noqa: E402  (added for phrase-level routing)

# คำหมวดที่ยอมให้ match แบบ substring ได้ (สำหรับกู้กรณีตัวตัดคำ "รวมคำ" เช่น
# "พนักงานบริการ" ที่ไม่ตรงตัวกับ "พนักงาน"/"บริการ")
#
# จำกัดเฉพาะ "คำนามหัวหมวด" ที่ไม่กำกวม — ไม่ไปโผล่เป็นส่วนหนึ่งของคำอื่นที่คนละความหมาย
# เหตุที่ไม่ใช้เกณฑ์ความยาวล้วน ๆ: ในภาษาไทยวรรณยุกต์/สระนับเป็นตัวอักษรด้วย ทำให้
# คำขั้วสั้นอย่าง "เย็น"(4) "ร้อน"(4) ยาวพอ ๆ กับคำนาม แต่ "เย็น" ดันไป match "เย็นชืด"
# (อาหารเย็นชืด = หมวดอาหาร ไม่ใช่บรรยากาศ) จึงคัดเฉพาะคำนามหัวหมวดที่ปลอดภัยแทน
_SUBSTR_SAFE = {
    "อาหาร", "รสชาติ", "วัตถุดิบ", "เครื่องดื่ม", "ของหวาน", "เครื่องปรุง",
    "บริการ", "พนักงาน", "เด็กเสิร์ฟ",
    "บรรยากาศ", "ที่จอดรถ", "ห้องน้ำ",
}


def detect_aspects(review: dict) -> list:
    """
    คืนรายการหมวดที่รีวิวนี้กล่าวถึง เช่น ["food", "service"]

    กติกาการ match (จากแม่นไปหลวม):
      1) token ตรงตัวกับคำในพจนานุกรมหมวด (token-equality) — แม่นที่สุด
      2) เฉพาะ "คำนามหัวหมวดที่ปลอดภัย" (_SUBSTR_SAFE) เป็น substring ของ token
         (กู้กรณีตัวตัดคำรวมคำ เช่น "พนักงานบริการ" ให้ยังนับเป็นบริการ)
    ใช้ tokens_base (ก่อนรวม negation) เพื่อให้คำหมวดเดิม เช่น "อร่อย" ยังจับได้
    """
    tokens = review.get("tokens_base") or review.get("tokens", [])
    token_set = set(tokens)
    found = []
    for aspect, words in ASPECT_LEXICON.items():
        hit = any(
            w in token_set
            or (w in _SUBSTR_SAFE and any(w in tok for tok in tokens))
            for w in words
        )
        if hit:
            found.append(aspect)
    return found


def tag_aspects(reviews: list) -> list:
    """
    ใส่ key 'aspects' ให้ทุกอนุประโยค และรวมเป็น aspects ระดับรีวิว (union)
    ถ้ารีวิวไม่มี clauses (กรณีเก่า/พิเศษ) จะ fallback มาจับจากทั้งรีวิว
    """
    for r in reviews:
        clauses = r.get("clauses")
        if clauses:
            union = []
            for c in clauses:
                c["aspects"] = detect_aspects(c) or ["uncategorized"]
                for a in c["aspects"]:
                    if a not in union:
                        union.append(a)
            # ตัด uncategorized ออกถ้ามีหมวดจริงปนอยู่ด้วย
            real = [a for a in union if a != "uncategorized"]
            r["aspects"] = real if real else ["uncategorized"]
        else:
            aspects = detect_aspects(r)
            r["aspects"] = aspects if aspects else ["uncategorized"]
    return reviews


def aspect_sentiment_summary(reviews: list) -> dict:
    """
    สรุปจำนวนอารมณ์ราย aspect — นับ "ตามอนุประโยค" ไม่ใช่ broadcast อารมณ์ทั้งรีวิว
    (อนุประโยคที่ชมอาหารจะไม่ทำให้ "บริการ" ที่ถูกเอ่ยถึงเฉย ๆ กลายเป็นบวก)

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
        clauses = r.get("clauses")
        if clauses:
            for c in clauses:
                sent = c.get("sentiment", "neutral")
                for a in c.get("aspects", []):
                    if a in summary:
                        summary[a][sent] += 1
                        summary[a]["total"] += 1
        else:
            # fallback: พฤติกรรมเดิม (ระดับรีวิว)
            sent = r.get("sentiment", "neutral")
            for a in r.get("aspects", []):
                if a in summary:
                    summary[a][sent] += 1
                    summary[a]["total"] += 1
    return summary


def detect_clause_aspects(clause: dict) -> list:
    """Aspects a clause talks about, from head nouns + descriptor hints over its raw
    tokens. Order-stable, de-duplicated."""
    toks = clause.get("raw_tokens") or clause.get("tokens_base") or []
    found = []
    for t in toks:
        a = lexicon.NOUN_TO_ASPECT.get(t) or lexicon.DESCRIPTOR_ASPECT_HINTS.get(t)
        if a and a not in found:
            found.append(a)
    return found


def route_aspect(phrase, clause_aspects: list):
    """4-tier resolver: idiom/concept -> head noun -> single clause aspect -> hint.
    Returns (aspect|None, conf)."""
    # tier 1 — curated mappings (idiom or synonym concept)
    if phrase.pattern == "idiom" and phrase.surface in lexicon.IDIOMS:
        return lexicon.IDIOMS[phrase.surface]["aspect"], "high"
    if phrase.concept in lexicon.SYNONYM_GROUPS:
        return lexicon.SYNONYM_GROUPS[phrase.concept]["aspect"], "high"
    # tier 2 — head noun
    if phrase.head_noun and phrase.head_noun in lexicon.NOUN_TO_ASPECT:
        return lexicon.NOUN_TO_ASPECT[phrase.head_noun], "high"
    # tier 3 — unambiguous clause context only
    if len(clause_aspects) == 1:
        return clause_aspects[0], "high"
    # tier 4 — descriptor hint
    for t in phrase.descriptor_tokens:
        if t in lexicon.DESCRIPTOR_ASPECT_HINTS:
            return lexicon.DESCRIPTOR_ASPECT_HINTS[t], "medium"
    joined = "".join(phrase.descriptor_tokens)
    if joined in lexicon.DESCRIPTOR_ASPECT_HINTS:
        return lexicon.DESCRIPTOR_ASPECT_HINTS[joined], "medium"
    return None, "low"
