"""
insights.py
===========
สร้าง "ข้อสรุปเชิงปฏิบัติ" (Actionable Insights) แบบ rule-based ราย aspect
นี่คือส่วนที่ทำให้ชื่อเรื่อง "กลยุทธ์" เป็นจริง: ระบบไม่ได้แค่บอก %
แต่บอกว่า "ด้านไหนเป็นจุดแข็ง / ด้านไหนต้องปรับ" พร้อมคำสำคัญประกอบ

หลักการ:
- คำนวณสัดส่วน positive/negative ของแต่ละ aspect
- ใช้ threshold ตัดสินว่าเป็น จุดแข็ง / ควรปรับปรุง / ปกติ
- ดึง keyword เชิงลบที่พบบ่อยมาประกอบคำแนะนำ

ฟังก์ชันหลัก: generate_insights(aspect_summary, keywords) -> list[dict]

หมายเหตุ (Phase 3): สามารถต่อยอดเป็นการเรียก LLM สรุปเป็นภาษาธรรมชาติได้
"""
from core.lexicon import ASPECT_LABELS_TH
from core.audience_insights import strategy_for_issue

# เกณฑ์ตัดสิน (ปรับได้)
STRONG_THRESHOLD = 0.65     # positive ratio >= นี้ -> จุดแข็ง
WEAK_THRESHOLD = 0.30       # negative ratio >= นี้ -> ควรปรับปรุง
MIN_SAMPLE = 5              # ต้องมีรีวิวอย่างน้อยกี่รายการถึงจะสรุป


def _top_negative_words(keywords_for_aspect: dict, n: int = 3) -> list:
    neg = keywords_for_aspect.get("negative", [])
    return [k["word"] for k in neg[:n]]


def _top_evidence(keywords_for_aspect: dict, sentiment: str, n: int = 3) -> list:
    evidence = []
    for item in keywords_for_aspect.get(sentiment, [])[:n]:
        if not item.get("word"):
            continue
        review_ids = list(dict.fromkeys(item.get("evidence_review_ids") or []))
        evidence.append({
            "text": item["word"],
            "count": max(1, int(item.get("count") or 1)),
            "review_count": int(item.get("review_count") or len(review_ids)),
            "evidence_review_ids": review_ids,
        })
    return evidence


def _evidence_ids(evidence: list) -> list[str]:
    """Return stable unique review IDs across the evidence phrases."""
    return list(dict.fromkeys(
        review_id
        for item in evidence
        for review_id in item.get("evidence_review_ids", [])
    ))


def _strength_strategy(aspect: str, evidence: list) -> str:
    focus = ", ".join(item["text"] for item in evidence[:2])
    strategies = {
        "food": "ล็อกสูตรและมาตรฐานวัตถุดิบของจุดที่ลูกค้าชม พร้อมใช้เมนูเด่นเหล่านี้เป็นตัวนำในการสื่อสารการตลาด",
        "service": "ถอดพฤติกรรมบริการที่ลูกค้าชมเป็น service playbook ใช้สอนพนักงานใหม่และตรวจซ้ำในช่วงลูกค้าหนาแน่น",
        "ambience": "รักษาจุดสัมผัสของบรรยากาศด้วย checklist และนำจุดเด่นไปใช้ในภาพถ่าย/ข้อความประชาสัมพันธ์อย่างสม่ำเสมอ",
    }
    strategy = strategies.get(aspect, "รักษามาตรฐานของจุดที่ลูกค้าชมและติดตามแนวโน้มทุกเดือน")
    return f"{strategy} จุดที่ควรโฟกัส: {focus}" if focus else strategy


def generate_insights(aspect_summary: dict, keywords: dict) -> list:
    """
    คืนรายการ insight:
    [
      {
        "aspect": "service",
        "aspect_th": "บริการ",
        "level": "improve" | "strength" | "neutral" | "insufficient",
        "positive_pct": int,
        "negative_pct": int,
        "message": "ข้อความสรุป",
        "keywords": ["รอนาน", ...]
      }, ...
    ]
    """
    insights = []
    for aspect, counts in aspect_summary.items():
        total = counts["total"]
        aspect_th = ASPECT_LABELS_TH.get(aspect, aspect)

        if total < MIN_SAMPLE:
            insights.append({
                "aspect": aspect,
                "aspect_th": aspect_th,
                "level": "insufficient",
                "positive_pct": 0,
                "negative_pct": 0,
                "message": f"ข้อมูลด้าน{aspect_th}ยังน้อย (พบความเห็นที่กล่าวถึง {total} ครั้ง) "
                           f"ยังสรุปแนวโน้มได้ไม่ชัด",
                "reason": f"พบความเห็นด้าน{aspect_th}เพียง {total} ครั้ง",
                "strategy": "เก็บรีวิวเพิ่มก่อนตัดสินใจเปลี่ยนกลยุทธ์ และติดตามสัญญาณเดิมซ้ำในรอบถัดไป",
                "evidence": [],
                "evidence_review_ids": [],
                "keywords": [],
            })
            continue

        pos_ratio = counts["positive"] / total
        neg_ratio = counts["negative"] / total
        pos_pct = round(pos_ratio * 100)
        neg_pct = round(neg_ratio * 100)
        aspect_keywords = keywords.get(aspect, {})
        neg_words = _top_negative_words(aspect_keywords)

        if neg_ratio >= WEAK_THRESHOLD:
            level = "improve"
            evidence = _top_evidence(aspect_keywords, "negative")
            kw_text = ("โดยเฉพาะเรื่อง " + ", ".join(neg_words)) if neg_words else ""
            reason = (f"ด้าน{aspect_th}มีความไม่พอใจ {neg_pct}% "
                      f"{kw_text}".strip())
            message = reason
            strategy = strategy_for_issue(neg_words[0] if neg_words else "", aspect)
        elif pos_ratio >= STRONG_THRESHOLD:
            level = "strength"
            evidence = _top_evidence(aspect_keywords, "positive")
            evidence_text = ", ".join(
                f"{item['text']} ({item['count']})" for item in evidence
            )
            reason = (f"ด้าน{aspect_th}เป็นจุดแข็ง เพราะมีความเห็นเชิงบวก {pos_pct}%"
                      + (f" โดยลูกค้าชมเรื่อง {evidence_text}" if evidence_text else ""))
            message = reason
            strategy = _strength_strategy(aspect, evidence)
        else:
            level = "neutral"
            evidence = (
                _top_evidence(aspect_keywords, "negative", 2)
                or _top_evidence(aspect_keywords, "positive", 2)
            )
            reason = (f"ด้าน{aspect_th}ยังไม่มีสัญญาณนำชัดเจน "
                      f"(บวก {pos_pct}% / ลบ {neg_pct}%)")
            message = reason
            strategy = strategy_for_issue(
                evidence[0]["text"] if evidence else "", aspect
            )

        insights.append({
            "aspect": aspect,
            "aspect_th": aspect_th,
            "level": level,
            "positive_pct": pos_pct,
            "negative_pct": neg_pct,
            "message": message,
            "reason": reason,
            "strategy": strategy,
            "evidence": evidence,
            "evidence_review_ids": _evidence_ids(evidence),
            "keywords": neg_words,
        })

    # เรียงให้ "ควรปรับปรุง" ขึ้นก่อน เพื่อให้เจ้าของร้านเห็นสิ่งที่ต้องแก้ทันที
    order = {"improve": 0, "neutral": 1, "strength": 2, "insufficient": 3}
    insights.sort(key=lambda x: order.get(x["level"], 9))
    return insights
