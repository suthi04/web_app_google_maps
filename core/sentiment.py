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
from core.negation import starts_with_negator, word_polarity

_POS = set(SENTIMENT_WORDS["positive"])
_NEG = set(SENTIMENT_WORDS["negative"])

# label ที่โมเดล wisesight ใช้ -> map เป็น 3 คลาสของเรา
_WISESIGHT_MAP = {
    "pos": "positive", "positive": "positive",
    "neg": "negative", "negative": "negative",
    "neu": "neutral", "neutral": "neutral",
    "q": "neutral", "question": "neutral",   # คลาส question -> neutral
}

_model_pipe = None    # cache โมเดล
_model_status = None  # None=ยังไม่ลอง, "ok"=โหลดได้, "failed"=โหลดไม่สำเร็จ
_unknown_label_warned = False  # เตือนเรื่อง label ที่แมปไม่ได้ครั้งเดียวพอ


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
    global _unknown_label_warned
    pipe = _load_model()
    out = pipe(clean_text[:512])          # ตัดความยาวกัน token เกิน
    raw = out[0]["label"].lower()
    if raw not in _WISESIGHT_MAP and not _unknown_label_warned:
        # กันบั๊กเงียบ: ถ้า checkpoint คืน label แบบ LABEL_0/1/2 (ไม่มี id2label)
        # ทุกอย่างจะถูกแมปเป็น neutral โดยไม่มี error -> ผล F1 เพี้ยนทั้งชุด
        _unknown_label_warned = True
        print(f"[sentiment] ⚠️  โมเดลคืน label ที่ไม่รู้จัก: {out[0]['label']!r} "
              f"-> แมปเป็น neutral. ตรวจ id2label ของ checkpoint "
              f"({config.MODEL_NAME}@{config.MODEL_REVISION})")
    return _WISESIGHT_MAP.get(raw, "neutral")


def _predict_lexicon(tokens: list) -> str:
    """fallback: นับคำบวก/ลบ (เข้าใจ negation ผ่าน negation.word_polarity) แล้วตัดสิน"""
    pos = sum(1 for t in tokens if word_polarity(t) > 0)
    neg = sum(1 for t in tokens if word_polarity(t) < 0)

    if pos == 0 and neg == 0:
        # เผื่อคำที่ไม่ถูกตัดแยก ลองเช็คแบบ substring กับข้อความรวม
        # ข้ามโทเคนที่ขึ้นต้นด้วยคำปฏิเสธ กันนับ "สะอาด" ใน "ไม่สะอาด" เป็นบวก
        joined = "".join(t for t in tokens if not starts_with_negator(t))
        pos = sum(1 for w in _POS if w in joined)
        neg = sum(1 for w in _NEG if w in joined)

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
    """
    ใส่ key 'sentiment' ให้รีวิวทุกรายการ (ระดับรีวิว — ใช้กับ donut/ตาราง)
    และให้ทุกอนุประโยค (ระดับ clause — ใช้กับสรุปอารมณ์ราย aspect ที่แม่นขึ้น)

    ออกแบบให้ระดับรีวิวยังทำงานเหมือนเดิม (อารมณ์รวมของทั้งรีวิว) เพื่อไม่ให้
    ภาพรวม/การกระจายอารมณ์เปลี่ยนพฤติกรรม ส่วนการแยกราย aspect ใช้อารมณ์ราย clause
    """
    for r in reviews:
        r["sentiment"] = predict(r)
        for c in r.get("clauses", []):
            c["sentiment"] = predict(c)
    return reviews


def engine_name() -> str:
    """บอกว่าตอนนี้ใช้เครื่องยนต์ไหนจริง ๆ (รายงานตามสถานะจริง ไม่หลอก)"""
    if not config.get_use_model():
        return "lexicon (พจนานุกรมคำ)"
    if _model_status == "failed":
        return "lexicon (WangchanBERTa โหลดไม่สำเร็จ)"
    return "WangchanBERTa"


def classify_phrase(phrase) -> str:
    """Stage 6 — sentiment for one phrase occurrence, independent of extraction.

    A phrase with a CLEAR polarity of its own (negation-aware) keeps that polarity —
    so "ราคาแพง" stays negative even inside a mostly-positive clause, and "ราคาไม่แพง"
    stays positive. Only phrases with NO inherent polarity (e.g. คนเยอะ) are decided
    from the source-clause CONTEXT (WangchanBERTa when on; lexicon when off).
    """
    global _model_status

    # 1) clear own polarity wins (joined so negation flips correctly: ไม่อร่อย -> neg)
    if phrase.descriptor_tokens:
        own = word_polarity("".join(phrase.descriptor_tokens))
        if own > 0:
            return "positive"
        if own < 0:
            return "negative"

    # 2) ambiguous phrase -> reuse the clause sentiment already computed in
    #    analyze_all (avoids a second, redundant model inference per phrase)
    clause = phrase.clause or {}
    cached = clause.get("sentiment")
    if cached in ("positive", "neutral", "negative"):
        return cached

    # 2b) no cached clause sentiment (e.g. clause-less phrase) -> compute now
    if config.get_use_model():
        try:
            return _predict_model(clause.get("clean", phrase.surface))
        except Exception as e:
            if _model_status != "failed":
                _model_status = "failed"
                print(f"[sentiment] WangchanBERTa unavailable, using lexicon: {e}")
    return _predict_lexicon(clause.get("tokens") or phrase.descriptor_tokens)