"""
negation.py
===========
จัดการคำปฏิเสธภาษาไทย (negation) ในระดับโทเคน

ปัญหาที่แก้:
    ตัวตัดคำ (newmm) แยก "ไม่อร่อย" -> ["ไม่", "อร่อย"] แล้วขั้นลบ stopword ทิ้ง "ไม่"
    เหลือ "อร่อย" ลอย ๆ -> รีวิว "อาหารไม่อร่อยเลย" กลายเป็นสัญญาณ "บวก" ผิดความหมาย
    (กระทบทั้งการจำแนกอารมณ์แบบ lexicon และคำสำคัญที่แสดงบนแดชบอร์ด)

วิธีแก้:
    รวม "คำปฏิเสธ" กับ "คำขั้ว (polar) ที่ตามมาทันที" ให้เป็นโทเคนเดียว
    เช่น ["ไม่", "อร่อย"] -> ["ไม่อร่อย"]  ซึ่งตรงกับคำใน lexicon (มี "ไม่อร่อย" อยู่แล้ว)
    และอ่านง่ายเมื่อนำไปแสดงเป็นคำสำคัญเชิงลบ

ออกแบบให้ทำงานก่อนขั้นลบ stopword (ดู core/preprocess.py) เพื่อให้ "ไม่" ที่ถูกรวมแล้ว
ไม่โดนทิ้ง ส่วน "ไม่" ที่ลอยเดี่ยว (ไม่ตามด้วยคำขั้ว) จะถูกลบเป็น stopword ตามปกติ

หมายเหตุการออกแบบ: รวม "เฉพาะ" เมื่อคำถัดไปเป็นคำขั้วที่รู้จัก (มาจาก SENTIMENT_WORDS
บวก/ลบ + คำขั้วเชิงหมวดบางคำ) เพื่อกันการรวมมั่ว เช่น "ไม่ร้าน" "ไม่โต๊ะ"
"""
from core.lexicon import SENTIMENT_WORDS

# คำปฏิเสธที่รองรับ (เรียงยาว->สั้น เพื่อใช้ตัด prefix ได้ถูกต้องในที่อื่น)
NEGATORS = ("ไม่ค่อย", "ไม่ได้", "ไม่มี", "ไม่", "ไร้")

# คำขั้ว (polar) ที่ยอมให้รวมหลังคำปฏิเสธ:
#   คำบวก/ลบทั้งหมดจาก lexicon + คำขั้วเชิงหมวดที่ไม่ได้อยู่ใน SENTIMENT_WORDS
#   ("เย็น" = แอร์เย็น/ความเย็นที่ดี -> "ไม่เย็น" สื่อความไม่พอใจ)
_EXTRA_POLAR = {"เย็น"}
_POLAR = set(SENTIMENT_WORDS["positive"]) | set(SENTIMENT_WORDS["negative"]) | _EXTRA_POLAR

_NEGATOR_SET = set(NEGATORS)

# เซ็ตคำบวก/ลบ (ใช้ตัดสินขั้วของโทเคน) — แหล่งความจริงเดียวให้ sentiment + การสกัดวลีใช้ร่วม
_POS = set(SENTIMENT_WORDS["positive"])
_NEG = set(SENTIMENT_WORDS["negative"])


def apply_negation(tokens: list) -> list:
    """
    รวมคำปฏิเสธกับคำขั้วที่ตามมาทันที -> โทเคนเดียว
    คืน list ใหม่ (ไม่แก้ของเดิม)
    """
    out = []
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        if tok in _NEGATOR_SET and i + 1 < n and tokens[i + 1] in _POLAR:
            out.append(tok + tokens[i + 1])
            i += 2
        else:
            out.append(tok)
            i += 1
    return out


def starts_with_negator(tok: str) -> bool:
    """โทเคนนี้ขึ้นต้นด้วยคำปฏิเสธหรือไม่ (เช่น 'ไม่อร่อย', 'ไม่สะอาด')"""
    return any(tok.startswith(p) and len(tok) > len(p) for p in NEGATORS)


def word_polarity(tok: str) -> int:
    """
    ขั้วของโทเคนเดียว: +1 บวก, -1 ลบ, 0 กลาง
    เข้าใจคำปฏิเสธที่ถูกรวมมาแล้ว (เช่น 'ไม่อร่อย', 'ไม่สะอาด') โดย "พลิกขั้ว" ของฐาน
    -> ปฏิเสธคำบวก = ลบ, ปฏิเสธคำลบ = บวก

    เป็นแหล่งความจริงเดียวเรื่อง "ขั้วของคำ" ใช้ร่วมกันทั้ง sentiment (lexicon) และ
    การสกัดวลี (ตัดสินว่า token เป็นคำบรรยายเชิงความเห็น/descriptor หรือไม่)
    """
    if tok in _NEG:
        return -1
    if tok in _POS:
        return 1
    for p in NEGATORS:                      # NEGATORS เรียงยาว->สั้นแล้ว
        if tok.startswith(p) and len(tok) > len(p):
            base = tok[len(p):]
            if base in _POS:
                return -1
            if base in _NEG:
                return 1
            return 0
    return 0
