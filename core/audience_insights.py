"""Build evidence-led views for consumers and restaurant operators.

The module is deterministic: every claim comes from persisted review text,
sentiment counts, or aggregated opinion phrases. It never fabricates a cause
or recommendation that is not connected to those signals.
"""

from core import practical_rules
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


def _practical_cautions(practical_insights: list[dict] | None) -> list[dict]:
    """Translate negative planning rules into the shared caution contract."""
    cautions = []
    for item in practical_insights or []:
        if item.get("status") not in {"negative", "mixed"}:
            continue
        review_count = int(item.get("review_count") or 0)
        negative_count = int(item.get("negative_review_count") or 0)
        negative_pct = round(negative_count / review_count * 100) if review_count else 0
        cautions.append({
            **item,
            "text": item.get("title") or item.get("text"),
            "count": review_count,
            "negative_pct": negative_pct,
            "severity": "critical" if review_count >= 2 else "watch",
            "source": "practical_rules",
        })
    return cautions


def _gemini_visit_tips(narrative: dict | None) -> list[dict]:
    """Adapt evidence-validated Gemini tips to the existing planning-card contract."""
    status_labels = {
        "positive": "ข้อมูลที่เป็นประโยชน์",
        "neutral": "ควรเช็กเพิ่ม",
        "negative": "ควรวางแผน",
    }
    action_tiers = {"positive": "ready", "neutral": "check", "negative": "plan"}
    items = []
    for item in (narrative or {}).get("visit_tips", []):
        sentiment = item.get("sentiment")
        evidence_ids = list(dict.fromkeys(item.get("evidence_review_ids") or []))
        if sentiment not in status_labels or not evidence_ids:
            continue
        aspect = item.get("aspect")
        text = item.get("title") or item.get("detail")
        items.append({
            **item,
            "topic": practical_rules.match_topic(
                f"{item.get('title', '')} {item.get('detail', '')}"
            ),
            "topic_label": ASPECT_LABELS_TH.get(aspect, aspect),
            "status": sentiment,
            "status_label": status_labels[sentiment],
            "action_tier": action_tiers[sentiment],
            "text": text,
            "summary": item.get("detail"),
            "count": len(evidence_ids),
            "review_count": len(evidence_ids),
            "evidence_review_ids": evidence_ids,
            "negative_review_count": len(evidence_ids) if sentiment == "negative" else 0,
            "positive_review_count": len(evidence_ids) if sentiment == "positive" else 0,
            "neutral_review_count": len(evidence_ids) if sentiment == "neutral" else 0,
            "context_labels": [],
            "query": text,
            "aspect_th": ASPECT_LABELS_TH.get(aspect, aspect),
            "source": "gemini",
        })
    return items


def _merge_planning_insights(
    practical_insights: list[dict] | None,
    narrative: dict | None,
    limit: int = 6,
) -> list[dict]:
    combined = [dict(item) for item in (practical_insights or [])]
    known_topics = {item.get("topic") for item in combined if item.get("topic")}
    for item in _gemini_visit_tips(narrative):
        if item.get("topic") and item["topic"] in known_topics:
            continue
        combined.append(item)
        if item.get("topic"):
            known_topics.add(item["topic"])
    for rank, item in enumerate(combined[:limit], start=1):
        item["rank"] = rank
    return combined[:limit]


def _cautions(
    keywords: dict,
    aspect_summary: dict,
    practical_insights: list[dict] | None = None,
    limit: int = 5,
) -> list[dict]:
    cautions = _practical_cautions(practical_insights)[:limit]
    if len(cautions) >= limit:
        return cautions
    seen_rule_topics = {item.get("topic") for item in cautions}
    seen_topics = set()
    for item in _phrase_items(keywords, {"negative"}):
        text = item["text"]
        matched_rule_topic = practical_rules.match_topic(text)
        if matched_rule_topic in seen_rule_topics:
            continue
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
    if cautions and cautions[0].get("advice"):
        detail += f" คำแนะนำ: {cautions[0]['advice']}"
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
    practical_insights: list[dict] | None = None,
    narrative: dict | None = None,
) -> dict:
    planning_insights = _merge_planning_insights(practical_insights, narrative)
    cautions = _cautions(keywords, aspect_summary, planning_insights)
    overview = (narrative or {}).get("overview") or {}
    lazy_summary = _lazy_summary(distribution, keywords, cautions, reviews)
    if overview.get("headline") and overview.get("detail"):
        lazy_summary = {
            "verdict": overview["headline"],
            "detail": overview["detail"],
            "evidence_review_ids": list(dict.fromkeys(
                overview.get("evidence_review_ids") or []
            )),
            "source": "gemini",
        }
    return {
        "things_to_know": planning_insights or _things_to_know(keywords),
        "lazy_summary": lazy_summary,
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
    if any(word in phrase for word in ("ที่จอด", "จอดรถ")):
        return "สำรวจจุดจอดใกล้ร้าน ทำข้อมูลเส้นทางและจุดจอดสำรองให้ชัด แล้วแจ้งลูกค้าก่อนช่วงเวลาหนาแน่น"
    if any(word in phrase for word in ("ทางเข้า", "หายาก", "ซอยลึก", "เดินทาง")):
        return "ตรวจหมุดและป้ายทางเข้า ทำภาพบอกทางจากจุดสังเกตหลัก และทดสอบเส้นทางด้วยผู้ที่ไม่เคยมาร้าน"
    if any(word in phrase for word in ("เงินสด", "บัตรเครดิต", "พร้อมเพย์", "จ่ายเงิน")):
        return "ระบุช่องทางชำระเงินให้ชัดทั้งหน้าร้านและออนไลน์ พร้อมตรวจอุปกรณ์และเตรียมช่องทางสำรองทุกกะ"
    if any(word in phrase for word in ("แพ้อาหาร", "เมนูเจ", "มังสวิรัติ", "วีแกน", "ฮาลาล")):
        return "ทำข้อมูลส่วนผสมและข้อจำกัดของเมนูให้ทีมตอบตรงกัน พร้อมขั้นตอนยืนยันความต้องการก่อนรับออเดอร์"
    fallbacks = {
        "food": "ตรวจตัวอย่างอาหารและ feedback รายเมนู หา root cause กับทีมครัว แล้วติดตามจำนวนคำร้องเรียนเดิมรายสัปดาห์",
        "service": "แยกปัญหาตามช่วงเวลาและขั้นตอนบริการ กำหนดเจ้าของปัญหา พร้อมตัวชี้วัดก่อน–หลังปรับปรุง",
        "ambience": "ตรวจ customer journey ตั้งแต่หน้าร้านถึงโต๊ะ ระบุจุดที่สร้างประสบการณ์ลบและแก้ทีละจุดพร้อมวัดผล",
    }
    return fallbacks.get(aspect, "ตรวจหลักฐานรีวิว หา root cause กับทีมที่เกี่ยวข้อง และติดตามผลด้วยตัวชี้วัดรายสัปดาห์")


def build_critical_issues(
    keywords: dict,
    aspect_summary: dict,
    practical_insights: list[dict] | None = None,
    limit: int = 6,
) -> list[dict]:
    issues = _cautions(
        keywords, aspect_summary, practical_insights=practical_insights, limit=20
    )
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


def _opportunity_action(aspect: str, topic: str) -> str:
    """Give owners a concrete way to turn an evidenced compliment into a system."""
    actions = {
        "food": (
            f"ยึด “{topic}” เป็นมาตรฐานของเมนูเด่น บันทึกสูตรและจุดตรวจคุณภาพ "
            "แล้วใช้คำชมนี้ช่วยสื่อสารเหตุผลที่ลูกค้าควรเลือกร้าน"
        ),
        "service": (
            f"ถอดพฤติกรรมที่ทำให้ลูกค้าพูดถึง “{topic}” เป็นขั้นตอนบริการสั้น ๆ "
            "เพื่อให้ทีมทำซ้ำได้สม่ำเสมอทุกกะ"
        ),
        "ambience": (
            f"รักษาจุดสัมผัสที่ทำให้เกิดคำชม “{topic}” แล้วนำไปใช้ในภาพร้าน "
            "ข้อมูลหน้าร้าน และเช็กลิสต์ก่อนเปิดบริการ"
        ),
    }
    return actions.get(
        aspect,
        f"ระบุสิ่งที่ทำให้เกิดคำชม “{topic}” แล้วเปลี่ยนเป็นมาตรฐานที่ทีมทำซ้ำและตรวจสอบได้",
    )


def build_operator_playbook(
    keywords: dict | None,
    critical_issues: list[dict] | None,
    limit_each: int = 4,
) -> dict:
    """Build issue-level moves without repeating the aspect-level roadmap."""
    risks = []
    for issue in critical_issues or []:
        evidence_ids = list(dict.fromkeys(issue.get("evidence_review_ids") or []))
        if not evidence_ids:
            continue
        review_count = int(issue.get("review_count") or len(evidence_ids))
        risks.append({
            "topic": issue.get("text") or "ประเด็นที่ควรตรวจสอบ",
            "aspect": issue.get("aspect") or "",
            "aspect_th": issue.get("aspect_th") or ASPECT_LABELS_TH.get(issue.get("aspect"), "ภาพรวม"),
            "review_count": review_count,
            "negative_pct": int(issue.get("negative_pct") or 0),
            "evidence_review_ids": evidence_ids,
            "action": issue.get("strategy") or strategy_for_issue(
                issue.get("text") or "", issue.get("aspect") or ""
            ),
            "signal_label": "พบซ้ำหลายรีวิว" if review_count >= 3 else "สัญญาณเบื้องต้น",
        })
    risks.sort(key=lambda item: (-item["review_count"], -item["negative_pct"], item["topic"]))

    opportunities = []
    for aspect, groups in (keywords or {}).items():
        for entry in groups.get("positive") or []:
            evidence_ids = list(dict.fromkeys(entry.get("evidence_review_ids") or []))
            topic = entry.get("word") or entry.get("text") or ""
            if not topic or not evidence_ids:
                continue
            review_count = int(entry.get("review_count") or len(evidence_ids))
            opportunities.append({
                "topic": topic,
                "aspect": aspect,
                "aspect_th": ASPECT_LABELS_TH.get(aspect, aspect),
                "review_count": review_count,
                "mention_count": int(entry.get("count") or review_count),
                "evidence_review_ids": evidence_ids,
                "action": _opportunity_action(aspect, topic),
                "signal_label": "จุดแข็งที่พูดซ้ำ" if review_count >= 3 else "โอกาสต่อยอด",
            })
    opportunities.sort(
        key=lambda item: (-item["review_count"], -item["mention_count"], item["topic"])
    )
    return {
        "risks": risks[:limit_each],
        "opportunities": opportunities[:limit_each],
    }


def build_operator_plan(
    actionable_insights: list[dict] | None,
    critical_issues: list[dict] | None,
    keywords: dict | None = None,
    distribution: dict | None = None,
    total_reviews: int = 0,
) -> dict:
    """Turn the owner report into one ranked, evidence-led action plan.

    Priority is based on the current review batch, never on calendar claims.  A
    problem needs at least three distinct supporting reviews and a strong
    negative ratio before it can be labelled as the first thing to handle.
    """
    issues_by_aspect: dict[str, list[dict]] = {}
    for issue in critical_issues or []:
        issues_by_aspect.setdefault(issue.get("aspect"), []).append(issue)

    items = []
    for insight in actionable_insights or []:
        aspect = insight.get("aspect")
        aspect_th = insight.get("aspect_th") or ASPECT_LABELS_TH.get(aspect, aspect)
        level = insight.get("level") or "insufficient"
        related_issue = (issues_by_aspect.get(aspect) or [{}])[0]
        insight_ids = insight.get("evidence_review_ids") or []
        issue_ids = related_issue.get("evidence_review_ids") or []
        evidence_ids = list(dict.fromkeys(
            [*insight_ids, *issue_ids]
            if level in ("improve", "neutral")
            else insight_ids
        ))
        evidence_count = len(evidence_ids)
        positive_pct = int(insight.get("positive_pct") or 0)
        negative_pct = int(insight.get("negative_pct") or 0)
        sample_size = int(insight.get("sample_size") or 0)
        evidence = insight.get("evidence") or []
        if level == "strength":
            topic = evidence[0].get("text") if evidence else ""
        else:
            topic = related_issue.get("text")
            if not topic:
                topic = evidence[0].get("text") if evidence else ""

        if level == "improve" and negative_pct >= 40 and evidence_count >= 3:
            priority = "first"
            priority_label = "ควรจัดการก่อน"
            score = 400 + negative_pct + min(evidence_count, 10) * 3
        elif level == "improve":
            priority = "improve"
            priority_label = "ควรปรับปรุง"
            score = 300 + negative_pct + min(evidence_count, 10) * 2
        elif level == "neutral":
            priority = "monitor"
            priority_label = "ควรติดตาม"
            score = 200 + negative_pct + evidence_count
        elif level == "strength":
            priority = "maintain"
            priority_label = "ควรรักษาไว้"
            score = 100 + positive_pct + evidence_count
        else:
            priority = "collect"
            priority_label = "เก็บข้อมูลเพิ่ม"
            score = sample_size

        if level == "improve":
            headline = topic or f"ลดเสียงลบด้าน{aspect_th}"
            measure = (
                f"วิเคราะห์ร้านเดิมในรอบถัดไป แล้วตรวจว่าเสียงลบด้าน{aspect_th}"
                + (f"และประเด็น “{topic}” " if topic else " ")
                + "ลดลงจากรอบนี้หรือไม่"
            )
        elif level == "strength":
            headline = topic or f"รักษาจุดแข็งด้าน{aspect_th}"
            measure = (
                f"วิเคราะห์ร้านเดิมในรอบถัดไป แล้วตรวจว่าเสียงบวกด้าน{aspect_th}"
                + (f"และคำชม “{topic}” " if topic else " ")
                + "ยังเป็นสัญญาณหลักอยู่หรือไม่"
            )
        elif level == "neutral":
            headline = topic or f"ติดตามเสียงลูกค้าด้าน{aspect_th}"
            measure = (
                f"เก็บรีวิวเพิ่ม แล้วตรวจว่าสัดส่วนเสียงบวกหรือลบด้าน{aspect_th}"
                "เริ่มเปลี่ยนไปทางใดทางหนึ่งชัดเจนหรือไม่"
            )
        else:
            headline = f"ข้อมูลด้าน{aspect_th}ยังไม่พอ"
            measure = (
                f"เก็บรีวิวที่กล่าวถึงด้าน{aspect_th}เพิ่มก่อน แล้วจึงประเมินใหม่"
                "โดยยังไม่รีบเปลี่ยนวิธีดำเนินงาน"
            )

        items.append({
            "aspect": aspect,
            "aspect_th": aspect_th,
            "priority": priority,
            "priority_label": priority_label,
            "score": score,
            "headline": headline,
            "reason": insight.get("reason") or insight.get("message") or "",
            "action": insight.get("strategy") or "",
            "measure": measure,
            "positive_pct": positive_pct,
            "negative_pct": negative_pct,
            "sample_size": sample_size,
            "evidence_review_ids": evidence_ids,
            "evidence_count": evidence_count,
            "source": insight.get("source") or "rule",
        })

    items.sort(key=lambda item: (-item["score"], item.get("aspect") or ""))
    for rank, item in enumerate(items, start=1):
        item["rank"] = rank

    counts = {
        key: sum(item["priority"] == key for item in items)
        for key in ("first", "improve", "monitor", "maintain", "collect")
    }
    playbook = build_operator_playbook(keywords, critical_issues)
    focus = next(
        (item for item in items if item["priority"] in ("first", "improve")),
        None,
    )
    strength = next((item for item in items if item["priority"] == "maintain"), None)
    if focus and strength:
        headline = f"เริ่มแก้{focus['aspect_th']} พร้อมใช้{strength['aspect_th']}เป็นแรงส่ง"
        detail = (
            f"เสียงลูกค้าในรีวิวชุดนี้ชี้ให้โฟกัส{focus['aspect_th']}ก่อน "
            f"ขณะเดียวกัน{strength['aspect_th']}มีฐานที่ควรรักษาและต่อยอดเป็นจุดจำของร้าน"
        )
    elif focus:
        headline = f"เริ่มจาก{focus['aspect_th']} แล้วตรวจผลจากรีวิวรอบถัดไป"
        detail = (
            f"ประเด็นด้าน{focus['aspect_th']}อยู่ลำดับแรกจากสัดส่วนความคิดเห็น "
            "จำนวนรีวิวไม่ซ้ำ และหลักฐานที่ตรวจย้อนกลับได้"
        )
    elif strength:
        headline = f"เปลี่ยน{strength['aspect_th']}ให้เป็นจุดจำที่ทำซ้ำได้"
        detail = (
            f"เสียงบวกด้าน{strength['aspect_th']}เป็นฐานที่เด่นในรีวิวชุดนี้ "
            "จึงควรถอดเป็นมาตรฐานและรักษาคุณภาพให้สม่ำเสมอ"
        )
    else:
        headline = "เก็บเสียงลูกค้าเพิ่ม ก่อนตัดสินใจเปลี่ยนร้าน"
        detail = "หลักฐานรายด้านยังไม่พอสำหรับชี้จุดเร่งด่วน ระบบจึงแนะนำให้ติดตามข้อมูลเพิ่มก่อน"

    all_evidence_ids = []
    for item in items:
        all_evidence_ids.extend(item.get("evidence_review_ids") or [])
    for group in (playbook["risks"], playbook["opportunities"]):
        for item in group:
            all_evidence_ids.extend(item.get("evidence_review_ids") or [])
    all_evidence_ids = list(dict.fromkeys(all_evidence_ids))
    total_reviews = int(total_reviews or (distribution or {}).get("total") or 0)
    positive_pct = int(((distribution or {}).get("pct") or {}).get("positive") or 0)
    return {
        "items": items,
        "counts": counts,
        "brief": {
            "headline": headline,
            "detail": detail,
            "positive_pct": positive_pct,
            "priority_count": counts["first"] + counts["improve"],
            "opportunity_count": len(playbook["opportunities"]),
            "evidence_count": len(all_evidence_ids),
            "total_reviews": total_reviews,
            "evidence_review_ids": all_evidence_ids,
        },
        "playbook": playbook,
        "next_checks": [
            {
                "rank": item["rank"],
                "aspect": item["aspect"],
                "aspect_th": item["aspect_th"],
                "measure": item["measure"],
            }
            for item in items[:3]
        ],
        "basis": "จัดอันดับจากสัดส่วนความคิดเห็น จำนวนรีวิวไม่ซ้ำ และหลักฐานในรีวิวชุดนี้",
    }


def enrich_result(result: dict) -> dict:
    """Add presentation fields to new or legacy persisted results in-place."""
    _prepare_evidence(result)
    practical_rules.enrich_result(result)
    result["sentiment_evidence"] = {
        sentiment: [
            review.get("review_id")
            for review in result.get("reviews") or []
            if review.get("sentiment") == sentiment and review.get("review_id")
        ]
        for sentiment in ("positive", "neutral", "negative")
    }
    narrative = result.get("analysis_narrative") or {}
    planning_insights = _merge_planning_insights(
        result.get("practical_insights") or [], narrative
    )
    result["consumer_summary"] = build_consumer_summary(
        result.get("keywords") or {},
        result.get("distribution") or {},
        result.get("aspect_summary") or {},
        result.get("reviews") or [],
        result.get("practical_insights") or [],
        narrative,
    )
    result["critical_issues"] = build_critical_issues(
        result.get("keywords") or {},
        result.get("aspect_summary") or {},
        planning_insights,
    )
    result["operator_plan"] = build_operator_plan(
        result.get("insights") or [],
        result["critical_issues"],
        result.get("keywords") or {},
        result.get("distribution") or {},
        result.get("total_reviews") or len(result.get("reviews") or []),
    )
    return result
