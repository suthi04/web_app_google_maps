"""
preprocess.py
=============
คัดกรอง + ทำความสะอาด + ตัดคำ ก่อนส่งเข้าวิเคราะห์

ขั้นตอน (ตามบทที่ 3 ในเล่ม):
1) is_thai()        คัดเฉพาะรีวิวภาษาไทย
2) clean_text()     ลบ URL, อีโมจิ, อักขระพิเศษ, normalize คำยืดเสียง
3) tokenize()       ตัดคำภาษาไทย (PyThaiNLP ถ้ามี ไม่งั้น fallback)
4) remove_stopwords ลบคำหยุด

ออกแบบให้ทำงานได้แม้ไม่มี PyThaiNLP (จะ fallback เป็นการตัดด้วยช่องว่าง)
แต่แนะนำให้ติดตั้ง pythainlp เพื่อผลที่ดีกว่า
"""
import re

# พยายาม import PyThaiNLP — ถ้าไม่มีก็ใช้ fallback
try:
    from pythainlp.tokenize import word_tokenize as _th_tokenize
    from pythainlp.corpus import thai_stopwords as _th_stopwords
    from pythainlp.util import normalize as _th_normalize
    _HAS_PYTHAINLP = True
    _STOPWORDS = set(_th_stopwords())
except Exception:  # pragma: no cover
    _HAS_PYTHAINLP = False
    _STOPWORDS = {
        "ที่", "ของ", "และ", "เป็น", "มี", "ได้", "ให้", "ใน", "กับ", "การ",
        "ก็", "จะ", "ไม่", "มา", "ว่า", "นี้", "นั้น", "แล้ว", "อยู่", "คือ",
    }

_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_EMOJI_RE = re.compile(
    "[" "\U0001F300-\U0001FAFF" "\U00002600-\U000027BF" "\U0001F1E6-\U0001F1FF" "]+",
    flags=re.UNICODE,
)
# เก็บเฉพาะอักษรไทย อังกฤษ ตัวเลข และช่องว่าง
_KEEP_RE = re.compile(r"[^\u0E00-\u0E7Fa-zA-Z0-9\s]")
_THAI_CHAR_RE = re.compile(r"[\u0E00-\u0E7F]")
_REPEAT_RE = re.compile(r"(.)\1{2,}")  # ตัวซ้ำ 3+ ตัว -> เหลือ 1 (อร่อยยยย -> อร่อย)


def is_thai(text: str, threshold: float = 0.2) -> bool:
    """รีวิวนับเป็นภาษาไทยถ้ามีสัดส่วนอักษรไทยถึงเกณฑ์"""
    if not text:
        return False
    thai_chars = len(_THAI_CHAR_RE.findall(text))
    total = len(re.sub(r"\s", "", text)) or 1
    return (thai_chars / total) >= threshold


def clean_text(text: str) -> str:
    """ลบ noise และ normalize ข้อความ"""
    text = _URL_RE.sub(" ", text)
    text = _EMOJI_RE.sub(" ", text)
    text = _REPEAT_RE.sub(r"\1", text)          # ลดคำยืดเสียง
    text = _KEEP_RE.sub(" ", text)              # ลบสัญลักษณ์พิเศษ
    text = re.sub(r"\s+", " ", text).strip()
    text = text.lower()                          # อังกฤษเป็นตัวเล็ก
    if _HAS_PYTHAINLP:
        try:
            text = _th_normalize(text)
        except Exception:
            pass
    return text


def tokenize(text: str) -> list:
    """ตัดคำภาษาไทย"""
    if _HAS_PYTHAINLP:
        return _th_tokenize(text, engine="newmm", keep_whitespace=False)
    return [t for t in text.split() if t]


def remove_stopwords(tokens: list) -> list:
    return [t for t in tokens if t not in _STOPWORDS and t.strip()]


def preprocess_review(text: str) -> dict:
    """
    เตรียมรีวิว 1 รายการ -> คืนทั้งข้อความสะอาดและ tokens
    {"clean": str, "tokens": [str, ...]}
    """
    cleaned = clean_text(text)
    tokens = remove_stopwords(tokenize(cleaned))
    return {"clean": cleaned, "tokens": tokens}


def filter_and_prepare(reviews: list) -> list:
    """
    รับรีวิวดิบ -> คัดเฉพาะไทย + เตรียมข้อมูล + ตัดซ้ำ
    คืน list ของ dict ที่มี key: text, rating, review_date, clean, tokens
    """
    seen = set()
    prepared = []
    for r in reviews:
        text = (r.get("text") or "").strip()
        if not text or not is_thai(text):
            continue
        if text in seen:                 # ตัดรีวิวซ้ำ
            continue
        seen.add(text)
        pp = preprocess_review(text)
        if not pp["clean"]:
            continue
        prepared.append({
            "text": text,
            "rating": r.get("rating"),
            "review_date": r.get("review_date"),
            "clean": pp["clean"],
            "tokens": pp["tokens"],
        })
    return prepared


def has_pythainlp() -> bool:
    return _HAS_PYTHAINLP
