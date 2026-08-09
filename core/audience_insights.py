"""Build evidence-led views for consumers and restaurant operators.

The module is deterministic: every claim comes from persisted review text,
sentiment counts, or aggregated opinion phrases. It never fabricates a cause
or recommendation that is not connected to those signals.
"""

from core.lexicon import ASPECT_LABELS_TH, SENTIMENT_WORDS
from core.practical_rules import build_practical_insights

_ISSUE_TOPICS = (
    "หวาน", "เค็ม", "เผ็ด", "จืด", "รอนาน", "ช้า", "แพง", "สกปรก",
    "ใส่ใจ", "ยิ้ม", "น้อย", "เสียงดัง", "ร้อน", "คิว",
)

# High-impact restaurant risks deserve a second, deliberately narrow pass over
# the original review text. Phrase extraction is optimized for opinion phrases
# and may legitimately drop a hygiene or food-safety statement. These rules use
# exact Thai cues and always retain the source review IDs; they do not infer a
# diagnosis or claim that the problem is widespread.
_REVIEW_RISK_RULES = (
    {
        "key": "pests",
        "text": "พบความเห็นเรื่องแมลงหรือสัตว์รบกวน",
        "query": "แมลง",
        "aspect": "ambience",
        "cues": ("แมลงวันตอม", "แมลงวันเยอะ", "แมลงสาบ", "หนูวิ่ง", "หนูในร้าน"),
        "priority": 40,
    },
    {
        "key": "food_spoilage",
        "text": "พบข้อกังวลว่าอาหารหรือวัตถุดิบอาจไม่สด",
        "query": "ไม่สด",
        "aspect": "food",
        "cues": ("อาหารบูด", "อาหารเสีย", "วัตถุดิบไม่สด", "ของไม่สด", "กลิ่นบูด"),
        "priority": 45,
    },
    {
        "key": "illness",
        "text": "มีผู้รีวิวกล่าวถึงอาการป่วยหลังรับประทาน",
        "query": "ท้องเสีย",
        "aspect": "food",
        "cues": ("อาหารเป็นพิษ", "กินแล้วท้องเสีย", "ทานแล้วท้องเสีย", "อาเจียนหลัง", "ปวดท้องหลัง"),
        "priority": 50,
    },
    {
        "key": "cleanliness",
        "text": "พบข้อกังวลเรื่องความสะอาด",
        "query": "สกปรก",
        "aspect": "ambience",
        "cues": ("ร้านสกปรก", "ไม่สะอาด", "ห้องน้ำสกปรก", "โต๊ะสกปรก", "โต๊ะเหนียว"),
        "priority": 35,
    },
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


def _things_to_know(
    keywords: dict,
    reviews: list | None = None,
    limit: int = 6,
) -> list[dict]:
    """Return restaurant planning topics backed by traceable review evidence.

    Unlike the old substring filter, this never falls back to generic praise
    such as "อาหารอร่อย" when no useful before-you-go information exists.
    """
    return build_practical_insights(
        reviews=reviews,
        phrase_items=_phrase_items(keywords),
        limit=limit,
    )


def _things_to_know_meta(items: list[dict]) -> dict:
    evidence_review_ids = list(dict.fromkeys(
        review_id
        for item in items
        for review_id in item.get("evidence_review_ids", [])
    ))
    return {
        "topic_count": len(items),
        "evidence_review_count": len(evidence_review_ids),
        "attention_count": sum(
            item.get("action_tier") == "plan" for item in items
        ),
        "repeated_count": sum(
            int(item.get("review_count") or 0) >= 2 for item in items
        ),
    }


def _evidence_level(review_count: int) -> tuple[str, str]:
    if review_count <= 1:
        return "preliminary", "พบใน 1 รีวิว — หลักฐานยังน้อย"
    if review_count <= 3:
        return "repeated", "พบซ้ำหลายรีวิว"
    return "frequent", "พบซ้ำอย่างต่อเนื่อง"


def _risk_cue_matches(text: str, cues: tuple[str, ...]) -> list[str]:
    compact = "".join(str(text or "").lower().split())
    matches = []
    for cue in cues:
        compact_cue = "".join(cue.lower().split())
        if compact_cue not in compact:
            continue
        negated = any(
            prefix + compact_cue in compact
            for prefix in ("ไม่มี", "ไม่เจอ", "ไม่พบ")
        )
        if not negated:
            matches.append(cue)
    return matches


def _review_risk_items(reviews: list | None, aspect_summary: dict) -> list[dict]:
    reviews = reviews or []
    risks = []
    for rule in _REVIEW_RISK_RULES:
        evidence_ids = []
        matched_cues = []
        for index, review in enumerate(reviews):
            matches = _risk_cue_matches(review.get("text", ""), rule["cues"])
            if not matches:
                continue
            review_id = str(review.get("review_id") or _stable_review_id(index))
            evidence_ids.append(review_id)
            matched_cues.extend(matches)
        evidence_ids = list(dict.fromkeys(evidence_ids))
        if not evidence_ids:
            continue

        counts = (aspect_summary or {}).get(rule["aspect"], {})
        total = int(counts.get("total") or 0)
        negative = int(counts.get("negative") or 0)
        negative_pct = round(negative / total * 100) if total else 0
        evidence_level, evidence_label = _evidence_level(len(evidence_ids))
        risks.append({
            "text": rule["text"],
            "query": rule["query"],
            "risk_key": rule["key"],
            "risk_priority": rule["priority"],
            "matched_cues": list(dict.fromkeys(matched_cues)),
            "count": len(evidence_ids),
            "review_count": len(evidence_ids),
            "evidence_review_ids": evidence_ids,
            "aspect": rule["aspect"],
            "aspect_th": ASPECT_LABELS_TH.get(rule["aspect"], rule["aspect"]),
            "sentiment": "negative",
            "negative_pct": negative_pct,
            "severity": "critical" if len(evidence_ids) >= 2 else "watch",
            "evidence_level": evidence_level,
            "evidence_label": evidence_label,
        })
    return risks


def _cautions(
    keywords: dict,
    aspect_summary: dict,
    reviews: list | None = None,
    limit: int = 5,
) -> list[dict]:
    phrase_cautions = []
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
        evidence_level, evidence_label = _evidence_level(item["review_count"])
        phrase_cautions.append({
            **item,
            "negative_pct": negative_pct,
            # A high negative ratio for the whole aspect must not turn a
            # one-review phrase into a "critical" claim.  Recurrence is based
            # on independent source reviews, not raw phrase occurrences.
            "severity": "critical" if item["review_count"] >= 2 else "watch",
            "evidence_level": evidence_level,
            "evidence_label": evidence_label,
            "risk_priority": 0,
        })

    review_risks = _review_risk_items(reviews, aspect_summary)
    # Prefer the clearer risk label when the extracted phrase expresses the
    # same cue from the same source review. Other issues in that review remain.
    for risk in review_risks:
        risk_ids = set(risk["evidence_review_ids"])
        phrase_cautions = [
            item for item in phrase_cautions
            if not (
                risk_ids.intersection(item.get("evidence_review_ids", []))
                and any(cue in item["text"] for cue in risk["matched_cues"])
            )
        ]

    cautions = review_risks + phrase_cautions
    cautions.sort(key=lambda item: (
        -(item["severity"] == "critical"),
        -int(item.get("risk_priority") or 0),
        -item["review_count"],
        -item["count"],
        item["text"],
    ))
    return cautions[:max(0, limit)]


def _summary_strengths(keywords: dict, limit: int = 2) -> list[dict]:
    """Return only repeated, traceable phrases suitable for a headline."""
    strengths = []
    for item in _phrase_items(keywords, {"positive"}):
        text = item["text"]
        if item["review_count"] < 2 or len(item["evidence_review_ids"]) < 2:
            continue
        if not (3 <= len(text) <= 60) or text[:1].isdigit():
            continue
        if any(word in text for word in SENTIMENT_WORDS["negative"]):
            continue
        strengths.append(item)
    strengths.sort(key=lambda item: (
        -item["review_count"], -item["count"], item["text"]
    ))
    return strengths[:max(0, limit)]


def _lazy_summary(
    distribution: dict,
    keywords: dict,
    cautions: list,
    reviews: list | None = None,
) -> dict:
    pct = (distribution or {}).get("pct", {})
    positive_pct = int(pct.get("positive") or 0)
    negative_pct = int(pct.get("negative") or 0)
    positives = _summary_strengths(keywords)
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
        detail += f" จุดที่มีคำชมซ้ำคือ {strengths}"
    detail += f"; ประเด็นที่ควรรู้คือ {warning}"
    evidence_review_ids = [
        review_id
        for item in positives
        for review_id in item.get("evidence_review_ids", [])
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
    cautions = _cautions(keywords, aspect_summary, reviews)
    things_to_know = _things_to_know(keywords, reviews)
    return {
        "things_to_know": things_to_know,
        "things_to_know_meta": _things_to_know_meta(things_to_know),
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


def build_critical_issues(
    keywords: dict,
    aspect_summary: dict,
    reviews: list | None = None,
    limit: int = 6,
) -> list[dict]:
    issues = _cautions(keywords, aspect_summary, reviews, limit=20)
    result = []
    for item in issues[:limit]:
        strategy = strategy_for_issue(item["text"], item["aspect"])
        if item["severity"] == "watch":
            strategy = (
                "ตรวจสอบว่าพบซ้ำในรีวิวใหม่หรือข้อมูลหน้างานก่อน "
                f"หากพบซ้ำจึงดำเนินการ: {strategy}"
            )
        if item["review_count"] <= 1:
            why = (
                f"พบใน 1 รีวิว และหลักฐานยังน้อย "
                f"จึงควรใช้เป็นสัญญาณเพื่อตรวจสอบ ไม่ใช่ข้อสรุปว่าร้านมีปัญหาทั่วไป"
            )
        else:
            why = (
                f"พบวลีนี้ {item['count']} ครั้ง จาก {item['review_count']} รีวิวไม่ซ้ำ "
                f"และความเห็นด้าน{item['aspect_th']}เป็นลบ {item['negative_pct']}%"
            )
        result.append({
            **item,
            "why": why,
            "strategy": strategy,
        })
    return result


def _rating_sentiment(rating) -> str | None:
    try:
        value = float(rating)
    except (TypeError, ValueError, OverflowError):
        return None
    if value >= 4:
        return "positive"
    if value <= 2:
        return "negative"
    return "neutral"


def enrich_result(result: dict) -> dict:
    """Add presentation fields to new or legacy persisted results in-place."""
    _prepare_evidence(result)
    mismatch_count = 0
    for review in result.get("reviews") or []:
        rating_sentiment = _rating_sentiment(review.get("rating"))
        text_sentiment = review.get("sentiment")
        mismatch = bool(
            rating_sentiment
            and text_sentiment in {"positive", "neutral", "negative"}
            and rating_sentiment != text_sentiment
        )
        review["rating_sentiment"] = rating_sentiment
        review["rating_sentiment_mismatch"] = mismatch
        mismatch_count += int(mismatch)
    result["rating_sentiment_mismatch_count"] = mismatch_count
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
        result.get("keywords") or {},
        result.get("aspect_summary") or {},
        result.get("reviews") or [],
    )
    return result
