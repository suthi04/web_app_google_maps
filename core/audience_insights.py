"""Build evidence-led views for consumers and restaurant operators.

The module is deterministic: every claim comes from persisted review text,
sentiment counts, or aggregated opinion phrases. It never fabricates a cause
or recommendation that is not connected to those signals.
"""

from core.lexicon import ASPECT_LABELS_TH, SENTIMENT_WORDS


_PRACTICAL_HINTS = {
    "รอนาน", "รอคิว", "ต้องรอ", "รออาหาร", "คิว", "ช้า", "เร็ว", "ช่วงพีค", "ที่จอดรถ", "จอดรถ", "ถนน",
    "หาง่าย", "เสียง", "ดัง", "แอร์", "ร้อน", "เย็น", "ราคา", "แพง",
    "สะอาด", "สกปรก", "ห้องน้ำ", "คนเยอะ", "ครอบครัว", "ถ่ายรูป",
}
_ISSUE_TOPICS = (
    "หวาน", "เค็ม", "เผ็ด", "จืด", "รอนาน", "ช้า", "แพง", "สกปรก",
    "ใส่ใจ", "ยิ้ม", "น้อย", "เสียงดัง", "ร้อน", "คิว",
)


def _stable_review_id(index: int) -> str:
    return f"R{index + 1:03d}"


def _prepare_evidence(result: dict) -> None:
    """Normalize review IDs and backfill exact evidence for legacy analyses.

    New analyses carry review provenance from extraction time.  Older persisted
    payloads do not, so we only backfill when the displayed phrase occurs
    verbatim in a review.  We intentionally avoid fuzzy guesses because a
    research citation that points at the wrong review is worse than no citation.
    """
    reviews = result.get("reviews") or []
    for index, review in enumerate(reviews):
        review.setdefault("review_id", _stable_review_id(index))

    for aspect, buckets in (result.get("keywords") or {}).items():
        for sentiment, phrases in (buckets or {}).items():
            for phrase in phrases or []:
                ids = list(dict.fromkeys(phrase.get("evidence_review_ids") or []))
                if not ids:
                    word = str(phrase.get("word") or "").strip()
                    ids = [
                        review["review_id"]
                        for review in reviews
                        if word
                        and word in str(review.get("text") or "")
                        and (not sentiment or review.get("sentiment") == sentiment)
                    ]
                phrase["evidence_review_ids"] = ids
                phrase["review_count"] = len(ids)


def _phrase_items(keywords: dict, sentiments=None) -> list[dict]:
    allowed = set(sentiments or ("positive", "neutral", "negative"))
    items = []
    for aspect, buckets in (keywords or {}).items():
        for sentiment, phrases in (buckets or {}).items():
            if sentiment not in allowed:
                continue
            for phrase in phrases or []:
                text = str(phrase.get("word") or "").strip()
                if not text:
                    continue
                items.append({
                    "text": text,
                    "count": max(1, int(phrase.get("count") or 1)),
                    "review_count": int(
                        phrase.get("review_count")
                        or len(phrase.get("evidence_review_ids") or [])
                    ),
                    "evidence_review_ids": list(dict.fromkeys(
                        phrase.get("evidence_review_ids") or []
                    )),
                    "aspect": aspect,
                    "aspect_th": ASPECT_LABELS_TH.get(aspect, aspect),
                    "sentiment": sentiment,
                })
    return sorted(items, key=lambda item: (-item["count"], item["text"]))


def _things_to_know(keywords: dict, limit: int = 6) -> list[dict]:
    items = _phrase_items(keywords)
    practical = [
        item for item in items
        if any(hint in item["text"] for hint in _PRACTICAL_HINTS)
    ]
    selected = practical or items
    return selected[:limit]


def _cautions(keywords: dict, aspect_summary: dict, limit: int = 5) -> list[dict]:
    cautions = []
    seen_topics = set()
    for item in _phrase_items(keywords, {"negative"}):
        text = item["text"]
        has_negative_cue = any(word in text for word in SENTIMENT_WORDS["negative"])
        has_negated_positive = any(
            f"ไม่{word}" in text for word in SENTIMENT_WORDS["positive"]
        )
        has_positive_cue = any(word in text for word in SENTIMENT_WORDS["positive"])
        # Legacy analyses may have inherited review-level polarity for every
        # phrase in a mixed review. Do not turn clearly positive evidence into
        # a red operator alert (for example, "ยิ้มแย้มดีมาก").
        if has_positive_cue and not (has_negative_cue or has_negated_positive):
            continue

        topic = next((term for term in _ISSUE_TOPICS if term in text), text)
        topic_key = (item["aspect"], topic)
        if topic_key in seen_topics:
            continue
        seen_topics.add(topic_key)

        counts = (aspect_summary or {}).get(item["aspect"], {})
        total = int(counts.get("total") or 0)
        negative = int(counts.get("negative") or 0)
        negative_pct = round(negative / total * 100) if total else 0
        cautions.append({
            **item,
            "negative_pct": negative_pct,
            # A high negative ratio for the whole aspect must not turn a
            # one-review phrase into a "critical" claim.  Recurrence is based
            # on independent source reviews, not raw phrase occurrences.
            "severity": "critical" if item["review_count"] >= 2 else "watch",
        })
        if len(cautions) >= limit:
            break
    return cautions


def _lazy_summary(
    distribution: dict,
    keywords: dict,
    cautions: list,
    reviews: list | None = None,
) -> dict:
    pct = (distribution or {}).get("pct", {})
    positive_pct = int(pct.get("positive") or 0)
    negative_pct = int(pct.get("negative") or 0)
    positives = _phrase_items(keywords, {"positive"})[:2]
    strengths = ", ".join(item["text"] for item in positives)
    warning = cautions[0]["text"] if cautions else "ยังไม่พบประเด็นลบเด่นชัด"

    if positive_pct >= 70:
        verdict = "เสียงส่วนใหญ่ชื่นชอบร้านนี้"
    elif negative_pct >= 30:
        verdict = "ควรอ่านข้อควรระวังก่อนตัดสินใจ"
    else:
        verdict = "ภาพรวมค่อนข้างผสม ควรเลือกตามสิ่งที่คุณให้ความสำคัญ"

    detail = f"รีวิวเชิงบวก {positive_pct}%"
    if strengths:
        detail += f" จุดที่ถูกชมบ่อยคือ {strengths}"
    detail += f"; ประเด็นที่ควรรู้คือ {warning}"
    evidence_review_ids = [
        review.get("review_id")
        for review in (reviews or [])
        if review.get("sentiment") == "positive" and review.get("review_id")
    ]
    # Mixed/negative summaries also need the caution sources supporting the
    # second half of the sentence.
    evidence_review_ids.extend(
        review_id
        for caution in cautions[:1]
        for review_id in caution.get("evidence_review_ids", [])
    )
    return {
        "verdict": verdict,
        "detail": detail,
        "evidence_review_ids": list(dict.fromkeys(evidence_review_ids)),
    }


def build_consumer_summary(
    keywords: dict,
    distribution: dict,
    aspect_summary: dict,
    reviews: list | None = None,
) -> dict:
    cautions = _cautions(keywords, aspect_summary)
    return {
        "things_to_know": _things_to_know(keywords),
        "lazy_summary": _lazy_summary(distribution, keywords, cautions, reviews),
        "cautions": cautions,
    }


def strategy_for_issue(text: str, aspect: str) -> str:
    phrase = (text or "").lower()
    if any(word in phrase for word in ("รอ", "ช้า", "คิว", "บริการไม่ทัน")):
        return "วัดเวลารอตามช่วงเวลา จัดกำลังคนช่วงพีค และตั้งเป้าเวลารับออเดอร์–เสิร์ฟที่ตรวจติดตามได้ทุกสัปดาห์"
    if any(word in phrase for word in ("หยาบคาย", "พูดจา", "ไม่สนใจ", "หน้าไม่พอใจ")):
        return "ทำ service playbook พร้อม role-play การรับเรื่องร้องเรียน และให้หัวหน้าสุ่มตรวจคุณภาพบริการรายกะ"
    if any(word in phrase for word in ("ไม่สด", "กลิ่น", "เค็ม", "จืด", "หวานเกิน", "รสชาติ")):
        return "กำหนดสูตรและจุดตรวจรสชาติ/วัตถุดิบก่อนเสิร์ฟ บันทึกล็อตที่มีปัญหา และทบทวนคำร้องเรียนกับครัวทุกวัน"
    if any(word in phrase for word in ("แพง", "ราคา", "ปริมาณ", "ไม่คุ้ม")):
        return "ทบทวนราคาเทียบปริมาณและต้นทุน สื่อสารคุณค่าของวัตถุดิบให้ชัด และทดลองชุดเมนูที่รับรู้ว่าคุ้มขึ้น"
    if any(word in phrase for word in ("สกปรก", "ห้องน้ำ", "โต๊ะ", "สะอาด")):
        return "ใช้ cleaning checklist ระบุผู้รับผิดชอบและเวลาตรวจ โดยให้หัวหน้ากะลงชื่อก่อนช่วงลูกค้าหนาแน่น"
    if any(word in phrase for word in ("เสียง", "ดัง", "ร้อน", "แอร์", "อึดอัด")):
        return "ตรวจสภาพพื้นที่ตามช่วงเวลา แยกโซนหรือปรับเสียง/อุณหภูมิ และเก็บ feedback หลังแก้เพื่อยืนยันผล"
    fallbacks = {
        "food": "ตรวจตัวอย่างอาหารและ feedback รายเมนู หา root cause กับทีมครัว แล้วติดตามจำนวนคำร้องเรียนเดิมรายสัปดาห์",
        "service": "แยกปัญหาตามช่วงเวลาและขั้นตอนบริการ กำหนดเจ้าของปัญหา พร้อมตัวชี้วัดก่อน–หลังปรับปรุง",
        "ambience": "ตรวจ customer journey ตั้งแต่หน้าร้านถึงโต๊ะ ระบุจุดที่สร้างประสบการณ์ลบและแก้ทีละจุดพร้อมวัดผล",
    }
    return fallbacks.get(aspect, "ตรวจหลักฐานรีวิว หา root cause กับทีมที่เกี่ยวข้อง และติดตามผลด้วยตัวชี้วัดรายสัปดาห์")


def build_critical_issues(keywords: dict, aspect_summary: dict, limit: int = 6) -> list[dict]:
    issues = _cautions(keywords, aspect_summary, limit=20)
    result = []
    for item in issues[:limit]:
        result.append({
            **item,
            "why": (
                f"พบวลีนี้ {item['count']} ครั้ง จาก {item['review_count']} รีวิวไม่ซ้ำ "
                f"และความเห็นด้าน{item['aspect_th']}"
                f"เป็นลบ {item['negative_pct']}%"
            ),
            "strategy": strategy_for_issue(item["text"], item["aspect"]),
        })
    return result


def enrich_result(result: dict) -> dict:
    """Add presentation fields to new or legacy persisted results in-place."""
    _prepare_evidence(result)
    result["sentiment_evidence"] = {
        sentiment: [
            review.get("review_id")
            for review in result.get("reviews") or []
            if review.get("sentiment") == sentiment and review.get("review_id")
        ]
        for sentiment in ("positive", "neutral", "negative")
    }
    result["consumer_summary"] = build_consumer_summary(
        result.get("keywords") or {},
        result.get("distribution") or {},
        result.get("aspect_summary") or {},
        result.get("reviews") or [],
    )
    result["critical_issues"] = build_critical_issues(
        result.get("keywords") or {}, result.get("aspect_summary") or {}
    )
    return result
