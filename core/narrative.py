"""
narrative.py
============
สร้าง "เนื้อหาเชิงเล่าเรื่อง" (narrative) สำหรับแดชบอร์ด 2 แท็บ:

  consumer     : สำหรับผู้บริโภค  -> tl_dr, top_mentions, things_to_know, warnings
  entrepreneur : สำหรับผู้ประกอบการ -> critical_points, actionable_insights (What/Why/How)

เครื่องยนต์หลักคือ Gemini (LLM) — ป้อนสรุป aspect + keyword + ตัวอย่างรีวิว แล้วให้
โมเดลเรียบเรียงเป็นภาษาธรรมชาติที่ "อ้างอิงจากรีวิวจริง" ไม่ใช่ประโยคสำเร็จรูปทื่อ ๆ
ตามแนวทางเดียวกับ core/phrases/llm_extract.py (lazy import, available(), response_schema).

ถ้าไม่มี GEMINI_API_KEY หรือเรียกไม่สำเร็จ -> ตกไปใช้ _fallback() ที่ derive จาก
keyword/insight แบบ rule-based เพื่อให้แดชบอร์ดยังมีเนื้อหาแสดง (โหมด demo ก็รันได้)

ฟังก์ชันหลัก: build(core) -> dict {"consumer": {...}, "entrepreneur": {...}, "engine": "..."}
โดย core = {store_name, distribution, aspect_summary, keywords, reviews}
"""
import json
import re
import time

import config
from core import insights as _insights
from core.lexicon import ASPECT_LABELS_TH

# retry เมื่อโดน rate-limit ชั่วคราว (per-minute) — โควตารายวันรอไปก็ 429 ซ้ำ จึงไม่รอ
_MAX_RETRIES = 2
_MAX_BACKOFF = 12        # วินาทีสูงสุดที่ยอมรอต่อครั้ง (กันหน้าเว็บค้าง)

# จำนวนรีวิวตัวอย่างที่ส่งให้ LLM (คุมความยาว prompt/ค่าใช้จ่าย)
_SAMPLE_REVIEWS = 24
_MAX_REVIEW_CHARS = 220

_SEVERITY = {"high", "medium", "low"}
_KIND = {"strength", "weakness"}

# ทำให้ aspect เป็น "คำเดียวไม่มีคำว่า ด้าน" เสมอ (UI เติม "ด้าน" ให้เอง)
_ASPECT_NORM = {
    "food": "อาหาร", "service": "บริการ",
    "ambience": "บรรยากาศ", "atmosphere": "บรรยากาศ",
    "value": "ความคุ้มค่า", "parking": "ที่จอดรถ",
}


def _norm_aspect(a):
    a = (a or "").strip()
    if a.startswith("ด้าน"):
        a = a[len("ด้าน"):].strip()
    return _ASPECT_NORM.get(a, a)

_SYSTEM = (
    "You are a Thai restaurant-review analyst writing dashboard copy in THAI. "
    "You produce two audiences of content from aggregated review data: "
    "(1) consumer-facing, friendly and skimmable; "
    "(2) owner-facing, sharp and operational. "
    "Ground EVERYTHING in the supplied keywords and sample reviews — never invent "
    "dishes, facts, or problems the data does not support. Write natural Thai, concise, "
    "no marketing fluff. For owner insights you MUST answer three distinct angles: "
    "อะไร (what — the concrete strength/weakness), ทำไม (why — the cause, citing review "
    "keywords), and กลยุทธ์ (how — a specific action to fix a weakness or amplify a "
    "strength to drive sales). Do NOT output flat lines like 'อาหารเป็นจุดแข็ง 99% ควรรักษาไว้'."
)

# Gemini response schema (OpenAPI-3 subset: no additionalProperties)
_SCHEMA = {
    "type": "object",
    "properties": {
        "consumer": {
            "type": "object",
            "properties": {
                "tl_dr": {"type": "string"},
                "top_mentions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": ["name", "reason"],
                    },
                },
                "things_to_know": {"type": "array", "items": {"type": "string"}},
                "warnings": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["tl_dr", "top_mentions", "things_to_know", "warnings"],
        },
        "entrepreneur": {
            "type": "object",
            "properties": {
                "critical_points": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "cause": {"type": "string"},
                            "strategy": {"type": "string"},
                            "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                        },
                        "required": ["title", "cause", "strategy", "severity"],
                    },
                },
                "actionable_insights": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "aspect": {"type": "string"},
                            "kind": {"type": "string", "enum": ["strength", "weakness"]},
                            "what": {"type": "string"},
                            "why": {"type": "string"},
                            "how": {"type": "string"},
                        },
                        "required": ["aspect", "kind", "what", "why", "how"],
                    },
                },
            },
            "required": ["critical_points", "actionable_insights"],
        },
    },
    "required": ["consumer", "entrepreneur"],
}


def available() -> bool:
    """True เฉพาะเมื่อมี API key และ import google-genai ได้ (เหมือน llm_extract)."""
    if not config.get_gemini_api_key():
        return False
    try:
        from google import genai  # noqa: F401
    except Exception:
        return False
    return True


def _client():
    from google import genai
    return genai.Client(api_key=config.get_gemini_api_key())


def _retry_after_seconds(err):
    """ดึงวินาทีที่ควรรอจาก error 429 ของ Gemini; คืน None ถ้าไม่ใช่ rate-limit."""
    s = str(err)
    if "RESOURCE_EXHAUSTED" not in s and "429" not in s:
        return None
    m = re.search(r"retry(?:Delay|\s+in)['\":\s]*([0-9]+(?:\.[0-9]+)?)s", s)
    return float(m.group(1)) if m else 0.0


def _generate(client, prompt):
    """เรียก Gemini พร้อม retry เฉพาะ rate-limit ชั่วคราวที่รอไม่นาน."""
    cfg = {
        "system_instruction": _SYSTEM,
        "response_mime_type": "application/json",
        "response_schema": _SCHEMA,
    }
    for attempt in range(_MAX_RETRIES + 1):
        try:
            return client.models.generate_content(
                model=config.GEMINI_MODEL, contents=prompt, config=cfg)
        except Exception as e:
            wait = _retry_after_seconds(e)
            if wait is not None and 0 <= wait <= _MAX_BACKOFF and attempt < _MAX_RETRIES:
                print(f"[narrative] rate-limited, retrying in {wait:.0f}s "
                      f"(attempt {attempt + 1}/{_MAX_RETRIES})")
                time.sleep(wait + 0.5)
                continue
            raise


# ---------------------------------------------------------------------------
# prompt building
# ---------------------------------------------------------------------------
def _kw_words(kw_for_aspect: dict, polarity: str, n: int = 6) -> list:
    return [k["word"] for k in (kw_for_aspect.get(polarity) or [])[:n]]


def _sample_reviews(reviews: list) -> list:
    """เลือกตัวอย่างรีวิวแบบคละอารมณ์ โดยดัน negative ขึ้นก่อน (สำคัญต่อจุดวิกฤต)."""
    order = {"negative": 0, "neutral": 1, "positive": 2}
    ranked = sorted(reviews, key=lambda r: order.get(r.get("sentiment"), 3))
    out = []
    for r in ranked[:_SAMPLE_REVIEWS]:
        text = (r.get("text") or r.get("clean") or "").replace("\n", " ").strip()
        if text:
            out.append(f"[{r.get('sentiment', '?')}] {text[:_MAX_REVIEW_CHARS]}")
    return out


def _build_prompt(core: dict) -> str:
    lines = [f"ร้าน: {core.get('store_name', '-')}"]
    dist = core.get("distribution", {}).get("pct", {})
    lines.append(
        f"สัดส่วนอารมณ์รวม: บวก {dist.get('positive', 0)}% / "
        f"กลาง {dist.get('neutral', 0)}% / ลบ {dist.get('negative', 0)}%"
    )
    kws = core.get("keywords", {})
    lines.append("\nสรุปราย aspect (พร้อมคำสำคัญที่ลูกค้าพูดถึง):")
    for aspect, counts in core.get("aspect_summary", {}).items():
        th = ASPECT_LABELS_TH.get(aspect, aspect)
        kw = kws.get(aspect, {})
        lines.append(
            f"- {th} ({aspect}): บวก {counts.get('positive', 0)} / "
            f"กลาง {counts.get('neutral', 0)} / ลบ {counts.get('negative', 0)} "
            f"(รวม {counts.get('total', 0)})"
        )
        pos, neg = _kw_words(kw, "positive"), _kw_words(kw, "negative")
        if pos:
            lines.append(f"    ชม: {', '.join(pos)}")
        if neg:
            lines.append(f"    ติ: {', '.join(neg)}")

    lines.append("\nตัวอย่างรีวิว (เรียง negative ก่อน):")
    lines.extend(_sample_reviews(core.get("reviews", [])))

    lines.append(
        "\nงาน: เขียน JSON ตาม schema เป็นภาษาไทย\n"
        "consumer.tl_dr: 2-3 ประโยค สรุปว่าร้านนี้เป็นยังไง เหมาะกับใคร\n"
        "consumer.top_mentions: จุดเด่นที่ลูกค้าชอบ/พูดถึงบ่อยในแง่ดี (name=จุดเด่นหรือธีม เช่น "
        "'รสชาติจัดจ้าน' 'ปริมาณคุ้มราคา'; ถ้ามีชื่อเมนูจริงในรีวิว เช่น 'ต้มยำกุ้ง' ให้ใช้ชื่อเมนูนั้น, "
        "reason=ทำไมคนชอบ) เอาเฉพาะที่มีในรีวิวจริง สูงสุด 5 รายการ\n"
        "consumer.things_to_know: เกร็ดก่อนไป เช่น ที่จอดรถ/ต้องจอง/ช่วงคนเยอะ/เสียงดัง เฉพาะที่รีวิวพูดถึง "
        "(ถ้าไม่มีให้เป็น list ว่าง)\n"
        "consumer.warnings: ข้อควรระวังจากรีวิวเชิงลบ สั้น ๆ\n"
        "entrepreneur.critical_points: จุดที่ต้องแก้ด่วน (title, cause=สาเหตุอ้างคีย์เวิร์ด, "
        "strategy=วิธีรับมือทันที, severity) เรียง high ก่อน\n"
        "entrepreneur.actionable_insights: ราย aspect ทั้งจุดแข็งและจุดอ่อน โดย "
        "aspect=หมวดคำเดียว (อาหาร/บริการ/บรรยากาศ ไม่ต้องมีคำว่า 'ด้าน'), "
        "what=สถานการณ์ (เกิดอะไรขึ้น), why=สาเหตุ (เพราะอะไร อ้างอิงคีย์เวิร์ดในรีวิว), "
        "how=แนวทาง (ควรทำอะไรต่อ)"
    )
    return "\n".join(lines)


def _sanitize(payload: dict) -> dict:
    """กันค่าที่ schema ยอมแต่เนื้อหาเพี้ยน (severity/kind นอกชุด, ตัดจำนวนรายการ)."""
    c = payload.get("consumer", {}) or {}
    e = payload.get("entrepreneur", {}) or {}

    def _clean_mentions(items):
        out = []
        for m in (items or [])[:5]:
            name = (m.get("name") or "").strip()
            if name:
                out.append({"name": name, "reason": (m.get("reason") or "").strip()})
        return out

    def _clean_strs(items, cap):
        return [s.strip() for s in (items or [])[:cap] if isinstance(s, str) and s.strip()]

    consumer = {
        "tl_dr": (c.get("tl_dr") or "").strip(),
        "top_mentions": _clean_mentions(c.get("top_mentions")),
        "things_to_know": _clean_strs(c.get("things_to_know"), 6),
        "warnings": _clean_strs(c.get("warnings"), 6),
    }

    crit = []
    for p in (e.get("critical_points") or [])[:6]:
        sev = p.get("severity") if p.get("severity") in _SEVERITY else "medium"
        title = (p.get("title") or "").strip()
        if title:
            crit.append({
                "title": title,
                "cause": (p.get("cause") or "").strip(),
                "strategy": (p.get("strategy") or "").strip(),
                "severity": sev,
            })

    ins = []
    for it in (e.get("actionable_insights") or [])[:8]:
        kind = it.get("kind") if it.get("kind") in _KIND else "weakness"
        what = (it.get("what") or "").strip()
        if what:
            ins.append({
                "aspect": _norm_aspect(it.get("aspect")),
                "kind": kind,
                "what": what,
                "why": (it.get("why") or "").strip(),
                "how": (it.get("how") or "").strip(),
            })

    entrepreneur = {"critical_points": crit, "actionable_insights": ins}
    return {"consumer": consumer, "entrepreneur": entrepreneur}


# ---------------------------------------------------------------------------
# rule-based fallback (โหมด demo / เมื่อ LLM ไม่พร้อม)
# ---------------------------------------------------------------------------
# เกร็ด "รู้ไว้ก่อนไป" ที่ derive ได้จากคำในรีวิว (trigger substrings -> ข้อความ)
_KNOW_HINTS = [
    (("จอดรถ", "ที่จอด", "ลานจอด"), "เรื่องที่จอดรถถูกพูดถึงในรีวิว — เผื่อเวลาหาที่จอด"),
    (("จอง", "คิว", "รอโต๊ะ", "รอนาน", "รอคิว"), "ช่วงคนเยอะอาจต้องรอคิว จองล่วงหน้าจะสบายกว่า"),
    (("เสียงดัง",), "ร้านค่อนข้างเสียงดังในบางช่วง"),
    (("คนเยอะ", "แน่น", "เต็มร้าน"), "ช่วงพีคคนค่อนข้างเยอะ ลองเลี่ยงชั่วโมงเร่งด่วน"),
    (("เผ็ด",), "บางเมนูรสจัด/เผ็ด สั่งเผื่อบอกระดับความเผ็ด"),
    (("แพง", "ราคา"), "เรื่องราคาถูกพูดถึงบ่อย — ดูเมนู/ราคาก่อนไปได้"),
]

# กลยุทธ์แก้ไขตามธีมของคำติ (trigger substrings -> วิธีที่จับต้องได้)
_FIX_HINTS = [
    (("รอ", "ช้า", "นาน", "คิว"),
     "ปรับระบบคิว/เพิ่มกำลังคนช่วงพีค และแจ้งเวลารอโดยประมาณให้ลูกค้า"),
    (("เสียง", "ดัง"),
     "จัดโซนแยกกลุ่มใหญ่ หรือเพิ่มวัสดุซับเสียงลดเสียงก้อง"),
    (("พนักงาน", "บริการ", "สนใจ", "ใส่ใจ", "หยาบ"),
     "เทรนพนักงานเรื่องการดูแล/ทักทาย และกำหนดผู้ดูแลประจำแต่ละโซน"),
    (("แพง", "ราคา", "คุ้ม"),
     "ทบทวนราคา/จัดเซตคุ้มค่า และสื่อสารความคุ้มให้ชัดขึ้น"),
    (("สะอาด", "เหนียว", "สกปรก", "ห้องน้ำ", "โต๊ะ"),
     "เพิ่มรอบทำความสะอาดโต๊ะ/ห้องน้ำ และตรวจเช็กก่อนเปิดร้าน"),
    (("รส", "เค็ม", "หวาน", "จืด", "มัน"),
     "ทบทวนสูตรและความสม่ำเสมอของรสชาติ ชิมก่อนเสิร์ฟทุกครั้ง"),
    (("ร้อน", "แอร์", "อากาศ"),
     "ปรับการระบายอากาศ/แอร์ให้เหมาะกับช่วงคนเยอะ"),
]


def _match_hints(words, hints):
    joined = " ".join(words)
    out = []
    for triggers, text in hints:
        if any(t in joined for t in triggers):
            out.append(text)
    return out


def _tone_phrase(pos, neg):
    if pos >= 65:
        return "ลูกค้าส่วนใหญ่ประทับใจ"
    if neg >= 40:
        return "รีวิวค่อนข้างผสม มีทั้งชมและติ"
    if pos >= 45:
        return "ภาพรวมค่อนไปทางบวก"
    return "ความเห็นค่อนข้างหลากหลาย"


def _fallback(core: dict) -> dict:
    kws = core.get("keywords", {})
    summary = core.get("aspect_summary", {})
    dist = core.get("distribution", {}).get("pct", {})
    pos_pct, neg_pct = dist.get("positive", 0), dist.get("negative", 0)

    # จุดเด่นที่ลูกค้าชอบ: คำชมของหมวดอาหาร (บ่อยสุดก่อน) — ธีม ไม่ใช่ชื่อเมนูตายตัว
    food_pos = (kws.get("food", {}).get("positive") or [])[:5]
    top_mentions = [
        {"name": k["word"], "reason": f"ลูกค้าพูดถึงในแง่ดี {k['count']} ครั้ง"}
        for k in food_pos
    ]

    # คำติเด่น ๆ ทุกหมวดรวมกัน (ใช้ทั้ง warnings และ things_to_know)
    neg_all = []
    for a, kw in kws.items():
        for k in (kw.get("negative") or [])[:3]:
            neg_all.append((k["count"], ASPECT_LABELS_TH.get(a, a), k["word"]))
    neg_all.sort(reverse=True)
    warnings = [f"ระวังเรื่อง{w} — พบในรีวิวด้าน{th} {c} ครั้ง" for c, th, w in neg_all[:5]]

    # รู้ไว้ก่อนไป: derive จากคำในรีวิว+คีย์เวิร์ดทั้งหมด (เฉพาะที่มีสัญญาณจริง)
    all_words = [w for _, _, w in neg_all]
    for a, kw in kws.items():
        for pol in ("positive", "neutral", "negative"):
            all_words += [k["word"] for k in (kw.get(pol) or [])]
    all_words += [(r.get("text") or "") for r in core.get("reviews", [])]
    things_to_know = _match_hints(all_words, _KNOW_HINTS)[:4]

    # TL;DR ที่อ่านเป็นประโยค ไม่ใช่ตัวเลขล้วน
    tl_dr = f"{_tone_phrase(pos_pct, neg_pct)} (บวก {pos_pct}%). "
    if top_mentions:
        tl_dr += f"จุดที่ถูกพูดถึงในแง่ดีบ่อยคือ{top_mentions[0]['name']} "
    if neg_all:
        tl_dr += f"ส่วนที่ควรเผื่อใจคือเรื่อง{neg_all[0][2]}"
    tl_dr = tl_dr.strip()

    # reuse rule-based insights แล้วแตกเป็น What/Why/How + critical points
    rule_insights = _insights.generate_insights(summary, kws)
    critical_points, actionable = [], []
    for ins in rule_insights:
        th = ins["aspect_th"]
        aspect = ins["aspect"]
        neg_words = ins.get("keywords") or []
        kw_text = ", ".join(neg_words)
        pos_words = [k["word"] for k in (kws.get(aspect, {}).get("positive") or [])[:2]]
        fixes = _match_hints(neg_words, _FIX_HINTS)
        fix_text = " / ".join(fixes[:2]) if fixes else \
            (f"เจาะแก้เรื่อง {kw_text} เป็นลำดับแรก" if kw_text else "ทบทวนขั้นตอนการทำงานด้านนี้")

        if ins["level"] == "improve":
            critical_points.append({
                "title": f"ด้าน{th}มีเสียงติค่อนข้างมาก ({ins['negative_pct']}% เชิงลบ)",
                "cause": f"ลูกค้าสะท้อนปัญหาเรื่อง {kw_text}" if kw_text else "พบรีวิวเชิงลบจำนวนมากในด้านนี้",
                "strategy": fix_text,
                "severity": "high" if ins["negative_pct"] >= 45 else "medium",
            })
            actionable.append({
                "aspect": th, "kind": "weakness",
                "what": f"ลูกค้าไม่พอใจราว {ins['negative_pct']}% ของรีวิวที่พูดถึงด้านนี้",
                "why": f"ประเด็นที่ถูกพูดถึงซ้ำ ๆ คือ {kw_text}" if kw_text
                       else "สัดส่วนความไม่พอใจสูงกว่าปกติ แม้ยังไม่มีคำติที่ชัดเจน",
                "how": fix_text + " จากนั้นสื่อสารการปรับปรุงให้ลูกค้ารับรู้",
            })
        elif ins["level"] == "strength":
            praise = f" โดยเฉพาะเรื่อง{', '.join(pos_words)}" if pos_words else ""
            actionable.append({
                "aspect": th, "kind": "strength",
                "what": f"ได้รับคำชมราว {ins['positive_pct']}% ของรีวิวที่พูดถึงด้านนี้{praise}",
                "why": "ลูกค้าพอใจอย่างต่อเนื่อง จนกลายเป็นภาพจำที่ดีของร้าน",
                "how": (f"ชูจุดที่ลูกค้าชม ({', '.join(pos_words)}) เป็นจุดขายในโฆษณา/โซเชียล "
                        if pos_words else "ใช้ด้านนี้เป็นจุดขายหลักในการโปรโมต ") +
                       "พร้อมรักษามาตรฐานให้คงที่",
            })

    return {
        "consumer": {
            "tl_dr": tl_dr,
            "top_mentions": top_mentions,
            "things_to_know": things_to_know,
            "warnings": warnings,
        },
        "entrepreneur": {
            "critical_points": critical_points,
            "actionable_insights": actionable,
        },
    }


# ---------------------------------------------------------------------------
# public
# ---------------------------------------------------------------------------
def build(core: dict) -> dict:
    """คืน narrative dict พร้อมฟิลด์ engine บอกว่ามาจาก LLM หรือ rule-based."""
    if available():
        try:
            resp = _generate(_client(), _build_prompt(core))
            data = _sanitize(json.loads(resp.text))
            data["engine"] = "gemini"
            return data
        except Exception as e:   # โควต้า/พาร์ส/เน็ต -> ตกไป rule-based กันแดชบอร์ดว่าง
            print(f"[narrative] Gemini failed, using rule-based fallback: {e}")

    data = _fallback(core)
    data["engine"] = "rule"
    return data
