"""
clause.py
=========
แบ่งรีวิวเป็น "อนุประโยค" (clause) ตามคำเชื่อมแสดงความขัดแย้ง

ทำไมต้องแบ่ง:
    รีวิวจริงมักพูดหลายหมวดในประโยคเดียว เช่น "อาหารอร่อย แต่บริการช้า"
    ถ้าตีอารมณ์ทั้งรีวิวเป็นก้อนเดียวแล้วโยนให้ทุกหมวด -> บริการจะถูกนับว่า "บวก"
    ทั้งที่จริงลูกค้าบ่นเรื่องบริการ การแบ่งอนุประโยคทำให้ผูกอารมณ์กับหมวดได้ตรงขึ้น
    (รากฐานของ aspect-level sentiment แบบเบา ไม่ต้องรื้อเป็น ABSA เต็มรูป)

ออกแบบให้ "อนุรักษ์นิยม": แบ่งเฉพาะคำเชื่อมขัดแย้งที่ชัดเจน (แต่ / แต่ว่า /
อย่างไรก็ตาม) ไม่แตะ "และ/แล้ว/ส่วน" ที่กำกวมเกินไป เพื่อกันการแบ่งผิด

ฟังก์ชันหลัก: split_clauses(text) -> list[str]
"""
import re

# คำเชื่อมขัดแย้ง (เรียงยาวก่อนสั้น เพื่อให้ "แต่ว่า" ถูกตัดก่อน "แต่")
_MARKERS = ["แต่ว่า", "อย่างไรก็ตาม", "แต่"]
_SPLIT_RE = re.compile("|".join(re.escape(m) for m in _MARKERS))


def split_clauses(text: str) -> list:
    """แบ่งข้อความเป็นอนุประโยค คืน list ที่ตัดช่องว่างหัวท้ายและทิ้งชิ้นว่างแล้ว"""
    if not text or not text.strip():
        return []
    parts = _SPLIT_RE.split(text)
    clauses = [p.strip() for p in parts if p and p.strip()]
    return clauses or [text.strip()]


# Marker tokens (token-level split — avoids the substring bug that mangled "ตกแต่ง")
_MARKER_TOKENS = {"แต่", "แต่ว่า", "อย่างไรก็ตาม"}


def split_clause_tokens(tokens: list) -> list:
    """Split a token list into clauses on contrastive marker *tokens* only.

    Operates on already-tokenized input, so "แต่" inside a word like "ตกแต่ง"
    (which the tokenizer keeps whole) is never treated as a boundary.
    Returns list[list[str]]; empty input -> [].
    """
    if not tokens:
        return []
    clauses, cur = [], []
    for t in tokens:
        if t in _MARKER_TOKENS:
            if cur:
                clauses.append(cur)
                cur = []
        else:
            cur.append(t)
    if cur:
        clauses.append(cur)
    return clauses or [list(tokens)]
