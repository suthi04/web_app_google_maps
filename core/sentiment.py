"""
sentiment.py
============
จำแนกอารมณ์รีวิวเป็น positive / neutral / negative

2 เครื่องยนต์ เลือกอัตโนมัติจาก config.USE_MODEL:
- โมเดลจริง  : WangchanBERTa (revision finetuned@wisesight_sentiment) ผ่าน transformers
               * โมเดลคืน 4 คลาส (pos/neu/neg/question) -> เราแมป "question" เป็น neutral
- fallback   : ให้คะแนนจากพจนานุกรมคำ (lexicon.py) — ใช้ตอน demo / ยังไม่ลงโมเดล
               เพื่อให้ทั้งระบบรันได้ทันที

ใช้แบบ singleton: โมเดลถูกโหลดครั้งเดียวตอนเรียกครั้งแรก (lazy load)
"""
import config
from core.lexicon import SENTIMENT_WORDS

# label ที่โมเดล wisesight ใช้ -> map เป็น 3 คลาสของเรา
_WISESIGHT_MAP = {
    "pos": "positive", "positive": "positive",
    "neg": "negative", "negative": "negative",
    "neu": "neutral", "neutral": "neutral",
    "q": "neutral", "question": "neutral",   # คลาส question -> neutral
}

_model_pipe = None    # cache โมเดล
_model_status = None  # None=ยังไม่ลอง, "ok"=โหลดได้, "failed"=โหลดไม่สำเร็จ


def _load_model():
    """โหลด WangchanBERTa ครั้งเดียว (lazy)"""
    global _model_pipe, _model_status
    if _model_pipe is not None:
        return _model_pipe
    from transformers import pipeline   # import ตอนใช้จริงเท่านั้น
    _model_pipe = pipeline(
        task="sentiment-analysis",
        model=config.MODEL_NAME,
        revision=config.MODEL_REVISION,
        tokenizer=config.MODEL_NAME,
    )
    _model_status = "ok"
    return _model_pipe


def _predict_model(clean_text: str) -> str:
    pipe = _load_model()
    out = pipe(clean_text[:512])          # ตัดความยาวกัน token เกิน
    raw = out[0]["label"].lower()
    return _WISESIGHT_MAP.get(raw, "neutral")


def _predict_lexicon(tokens: list) -> str:
    """fallback: นับคำบวก/ลบ แล้วตัดสิน"""
    pos = sum(1 for t in tokens if t in SENTIMENT_WORDS["positive"])
    neg = sum(1 for t in tokens if t in SENTIMENT_WORDS["negative"])
    # เผื่อคำที่ไม่ถูกตัดแยก ลองเช็คแบบ substring กับข้อความรวม
    joined = "".join(tokens)
    if pos == 0:
        pos = sum(1 for w in SENTIMENT_WORDS["positive"] if w in joined)
    if neg == 0:
        neg = sum(1 for w in SENTIMENT_WORDS["negative"] if w in joined)

    if pos == 0 and neg == 0:
        return "neutral"
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def predict(review: dict) -> str:
    """
    จำแนกอารมณ์รีวิว 1 รายการ
    review ต้องมี key: clean, tokens (จาก preprocess)
    """
    global _model_status
    if config.get_use_model():
        try:
            return _predict_model(review["clean"])
        except Exception as e:        # ถ้าโมเดลโหลด/ทำงานไม่ได้ -> fallback กันระบบล่ม
            if _model_status != "failed":
                _model_status = "failed"
                print(f"[sentiment] โหลด WangchanBERTa ไม่สำเร็จ ใช้ lexicon แทน: {e}")
                print("[sentiment] แก้: pip install -r requirements-model.txt")
    return _predict_lexicon(review["tokens"])


def analyze_all(reviews: list) -> list:
    """ใส่ key 'sentiment' ให้รีวิวทุกรายการ"""
    for r in reviews:
        r["sentiment"] = predict(r)
    return reviews


def engine_name() -> str:
    """บอกว่าตอนนี้ใช้เครื่องยนต์ไหนจริง ๆ (รายงานตามสถานะจริง ไม่หลอก)"""
    if not config.get_use_model():
        return "lexicon (พจนานุกรมคำ)"
    if _model_status == "failed":
        return "lexicon (WangchanBERTa โหลดไม่สำเร็จ)"
    return "WangchanBERTa"