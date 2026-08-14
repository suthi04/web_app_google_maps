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
import logging
import threading

import config
from core.lexicon import IDIOMS, SENTIMENT_WORDS
from core.negation import word_polarity

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
_model_load_lock = threading.Lock()
# สามารถดึงรีวิว/ทำ Rule-based/Gemini ได้พร้อมกัน 3 งาน แต่จำกัดช่วงที่กิน
# CPU/RAM มากที่สุดไว้ 2 งาน เพื่อให้เครื่อง 16 GB ไม่หน่วงจนเว็บล่ม
_model_inference_gate = threading.BoundedSemaphore(
    config.WANGCHAN_MAX_CONCURRENT
)
log = logging.getLogger(__name__)


def _build_model_pipeline():
    """Build the heavyweight pipeline behind a small, testable boundary."""
    from transformers import pipeline   # import ตอนใช้จริงเท่านั้น
    return pipeline(
        task="sentiment-analysis",
        model=config.MODEL_NAME,
        revision=config.MODEL_REVISION,
        tokenizer=config.MODEL_NAME,
    )


def _load_model():
    """โหลด WangchanBERTa ครั้งเดียว (lazy)"""
    global _model_pipe, _model_status
    if _model_pipe is not None:
        return _model_pipe
    # Double-check ใต้ lock ป้องกัน 2-3 worker โหลดโมเดลก้อนเดียวกันซ้ำพร้อมกัน
    # ซึ่งอาจทำให้ RAM พุ่งหลาย GB ในช่วงเริ่มงานแรก
    with _model_load_lock:
        if _model_pipe is not None:
            return _model_pipe
        _model_pipe = _build_model_pipeline()
        _model_status = "ok"
    return _model_pipe


def _label_from_output(output: dict) -> str:
    """แปลงผลจาก Hugging Face pipeline เป็น contract 3 คลาสของระบบ"""
    global _unknown_label_warned
    raw_label = str(output.get("label", ""))
    raw = raw_label.lower()
    if raw not in _WISESIGHT_MAP and not _unknown_label_warned:
        # กันบั๊กเงียบ: ถ้า checkpoint คืน label แบบ LABEL_0/1/2 (ไม่มี id2label)
        # ทุกอย่างจะถูกแมปเป็น neutral โดยไม่มี error -> ผล F1 เพี้ยนทั้งชุด
        _unknown_label_warned = True
        log.warning(
            "Unknown sentiment label %r; mapping to neutral. Check %s@%s id2label",
            raw_label,
            config.MODEL_NAME,
            config.MODEL_REVISION,
        )
    return _WISESIGHT_MAP.get(raw, "neutral")


def _predict_model(clean_text: str) -> str:
    with _model_inference_gate:
        pipe = _load_model()
        # ให้ tokenizer เป็นผู้ตัดตามจำนวน token จริง; การ slice 512 ตัวอักษรไม่รับประกัน
        # ว่าจะไม่เกิน model context โดยเฉพาะข้อความภาษาไทย
        out = pipe(clean_text, truncation=True, max_length=512)
    return _label_from_output(out[0])


def _idiom_polarity_counts(clean_text: str | None) -> tuple[int, int]:
    """Count curated expressions longest-first without double-counting overlap.

    This is intentionally text-aware: tokenization removes a standalone "ไม่"
    when it cannot merge with the next token, which would turn "ไม่จกตา" into
    "จกตา". Matching the original cleaned text preserves the phrase meaning.
    """
    compact = "".join((clean_text or "").split())
    if not compact:
        return 0, 0
    occupied = [False] * len(compact)
    pos = neg = 0
    expressions = [
        (surface, info.get("polarity", 0))
        for surface, info in IDIOMS.items()
        if info.get("polarity")
    ]
    for surface, polarity in sorted(expressions, key=lambda item: len(item[0]), reverse=True):
        start = 0
        while True:
            index = compact.find(surface, start)
            if index < 0:
                break
            end = index + len(surface)
            if not any(occupied[index:end]):
                occupied[index:end] = [True] * (end - index)
                if polarity > 0:
                    pos += 1
                else:
                    neg += 1
            start = index + 1
    return pos, neg


def _predict_lexicon(tokens: list, clean_text: str | None = None) -> str:
    """fallback: นับคำบวก/ลบ (เข้าใจ negation ผ่าน negation.word_polarity) แล้วตัดสิน"""
    pos = sum(1 for t in tokens if word_polarity(t) > 0)
    neg = sum(1 for t in tokens if word_polarity(t) < 0)

    phrase_pos, phrase_neg = _idiom_polarity_counts(clean_text)
    pos += phrase_pos
    neg += phrase_neg

    if pos == 0 and neg == 0:
        return "neutral"
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def predict(review: dict, use_model: bool | None = None) -> str:
    """
    จำแนกอารมณ์รีวิว 1 รายการ
    review ต้องมี key: clean, tokens (จาก preprocess)
    """
    global _model_status
    model_enabled = config.get_use_model() if use_model is None else use_model
    if model_enabled and _model_status != "failed":
        try:
            return _predict_model(review["clean"])
        except Exception as e:        # ถ้าโมเดลโหลด/ทำงานไม่ได้ -> fallback กันระบบล่ม
            if _model_status != "failed":
                _model_status = "failed"
                log.warning("WangchanBERTa unavailable; using lexicon: %s", e)
    return _predict_lexicon(review["tokens"], review.get("clean"))


def analyze_all(reviews: list, use_model: bool | None = None) -> list:
    """
    ใส่ key 'sentiment' ให้รีวิวทุกรายการ (ระดับรีวิว — ใช้กับ donut/ตาราง)
    และให้ทุกอนุประโยค (ระดับ clause — ใช้กับสรุปอารมณ์ราย aspect ที่แม่นขึ้น)

    ออกแบบให้ระดับรีวิวยังทำงานเหมือนเดิม (อารมณ์รวมของทั้งรีวิว) เพื่อไม่ให้
    ภาพรวม/การกระจายอารมณ์เปลี่ยนพฤติกรรม ส่วนการแยกราย aspect ใช้อารมณ์ราย clause
    """
    global _model_status
    model_enabled = config.get_use_model() if use_model is None else use_model
    targets = []
    for r in reviews:
        targets.append(r)
        targets.extend(r.get("clauses", []))

    # ส่งทั้งรีวิวและ clause ใน batch เดียว ลด Python/model overhead อย่างมาก
    # และทำให้ failure เกิดครั้งเดียวแทนการลองโหลดโมเดลซ้ำทุกข้อความ
    if model_enabled and _model_status != "failed" and targets:
        try:
            with _model_inference_gate:
                pipe = _load_model()
                outputs = pipe(
                    [item["clean"] for item in targets],
                    truncation=True,
                    max_length=512,
                    batch_size=16,
                )
            if len(outputs) != len(targets):
                raise RuntimeError(
                    f"โมเดลคืนผล {len(outputs)} รายการ แต่ส่งไป {len(targets)} รายการ"
                )
            for item, output in zip(targets, outputs):
                item["sentiment"] = _label_from_output(output)
            return reviews
        except Exception as e:
            _model_status = "failed"
            log.warning("WangchanBERTa batch failed; using lexicon: %s", e)

    for item in targets:
        item["sentiment"] = _predict_lexicon(item["tokens"], item.get("clean"))
    return reviews


def engine_name(use_model: bool | None = None) -> str:
    """บอกว่าตอนนี้ใช้เครื่องยนต์ไหนจริง ๆ (รายงานตามสถานะจริง ไม่หลอก)"""
    model_enabled = config.get_use_model() if use_model is None else use_model
    if not model_enabled:
        return "lexicon (พจนานุกรมคำ)"
    if _model_status == "failed":
        return "lexicon (WangchanBERTa โหลดไม่สำเร็จ)"
    return "WangchanBERTa"


def classify_phrase(phrase, use_model: bool | None = None) -> str:
    """Stage 6 — sentiment for one phrase occurrence, independent of extraction.

    A phrase with a CLEAR polarity of its own (negation-aware) keeps that polarity —
    so "ราคาแพง" stays negative even inside a mostly-positive clause, and "ราคาไม่แพง"
    stays positive. Only phrases with NO inherent polarity (e.g. คนเยอะ) are decided
    from the source-clause CONTEXT (WangchanBERTa when on; lexicon when off).
    """
    global _model_status

    # Curated multi-token expressions keep their explicit polarity. This covers
    # Thai phrases whose negator or slang is split into several tokenizer tokens.
    if phrase.pattern == "idiom" and phrase.surface in IDIOMS:
        polarity = IDIOMS[phrase.surface].get("polarity", 0)
        if polarity > 0:
            return "positive"
        if polarity < 0:
            return "negative"

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
    model_enabled = config.get_use_model() if use_model is None else use_model
    if model_enabled and _model_status != "failed":
        try:
            return _predict_model(clause.get("clean", phrase.surface))
        except Exception as e:
            if _model_status != "failed":
                _model_status = "failed"
                log.warning("WangchanBERTa unavailable; using lexicon: %s", e)
    return _predict_lexicon(
        clause.get("tokens") or phrase.descriptor_tokens,
        clause.get("clean", phrase.surface),
    )
