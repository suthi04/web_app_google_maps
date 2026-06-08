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

# เกณฑ์ตัดสิน (ปรับได้)
STRONG_THRESHOLD = 0.65     # positive ratio >= นี้ -> จุดแข็ง
WEAK_THRESHOLD = 0.30       # negative ratio >= นี้ -> ควรปรับปรุง
MIN_SAMPLE = 5              # ต้องมีรีวิวอย่างน้อยกี่รายการถึงจะสรุป


def _top_negative_words(keywords_for_aspect: dict, n: int = 3) -> list:
    neg = keywords_for_aspect.get("negative", [])
    return [k["word"] for k in neg[:n]]


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
                "message": f"ข้อมูลด้าน{aspect_th}ยังน้อย (พบ {total} รีวิว) "
                           f"ยังสรุปแนวโน้มได้ไม่ชัด",
                "keywords": [],
            })
            continue

        pos_ratio = counts["positive"] / total
        neg_ratio = counts["negative"] / total
        pos_pct = round(pos_ratio * 100)
        neg_pct = round(neg_ratio * 100)
        neg_words = _top_negative_words(keywords.get(aspect, {}))

        if neg_ratio >= WEAK_THRESHOLD:
            level = "improve"
            kw_text = ("โดยเฉพาะเรื่อง " + ", ".join(neg_words)) if neg_words else ""
            message = (f"ด้าน{aspect_th}มีความไม่พอใจค่อนข้างสูง "
                       f"({neg_pct}% เชิงลบ) ควรพิจารณาปรับปรุง {kw_text}".strip())
        elif pos_ratio >= STRONG_THRESHOLD:
            level = "strength"
            message = (f"ด้าน{aspect_th}เป็นจุดแข็งของร้าน "
                       f"({pos_pct}% เชิงบวก) ควรรักษามาตรฐานนี้ไว้")
        else:
            level = "neutral"
            message = (f"ด้าน{aspect_th}อยู่ในระดับปานกลาง "
                       f"(บวก {pos_pct}% / ลบ {neg_pct}%) ยังมีโอกาสพัฒนาเพิ่ม")

        insights.append({
            "aspect": aspect,
            "aspect_th": aspect_th,
            "level": level,
            "positive_pct": pos_pct,
            "negative_pct": neg_pct,
            "message": message,
            "keywords": neg_words,
        })

    # เรียงให้ "ควรปรับปรุง" ขึ้นก่อน เพื่อให้เจ้าของร้านเห็นสิ่งที่ต้องแก้ทันที
    order = {"improve": 0, "neutral": 1, "strength": 2, "insufficient": 3}
    insights.sort(key=lambda x: order.get(x["level"], 9))
    return insights
