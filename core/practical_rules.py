"""Deterministic restaurant rules for the consumer "before you go" view.

The rules do not invent restaurant facts.  A topic is emitted only when its
Thai cue occurs in a persisted review or an extracted phrase with traceable
review IDs.  Topic-level positive and negative evidence is kept separately so
contradictory reviews remain visible instead of being averaged away.
"""

from __future__ import annotations

import re
from collections import Counter


def _topic(
    key: str,
    label: str,
    decision_weight: int,
    positive: tuple[str, ...],
    negative: tuple[str, ...],
    factual: tuple[str, ...],
    titles: dict[str, str],
    advice: dict[str, str],
) -> dict:
    return {
        "key": key,
        "label": label,
        "decision_weight": decision_weight,
        "positive": positive,
        "negative": negative,
        "factual": factual,
        "titles": titles,
        "advice": advice,
    }


# The topic taxonomy is restaurant-only.  It is informed by restaurant ABSA
# datasets (see docs/practical-insights-rulebase.md), while the Thai cue lists
# are an auditable product rule set seeded from this project's review corpus.
PRACTICAL_TOPICS = (
    _topic(
        "dietary",
        "อาหารเฉพาะและอาการแพ้",
        30,
        ("มีเมนูเจ", "มีอาหารเจ", "มีมังสวิรัติ", "มีเมนูวีแกน", "มีฮาลาล", "อาหารฮาลาล"),
        ("ไม่มีเมนูเจ", "ไม่มีอาหารเจ", "ไม่มีมังสวิรัติ", "ไม่มีวีแกน", "ไม่ฮาลาล", "ไม่มีฮาลาล"),
        ("แพ้อาหาร", "แพ้ถั่ว", "แพ้กุ้ง", "แพ้อาหารทะเล", "กลูเตน", "มังสวิรัติ", "วีแกน", "ฮาลาล", "อาหารเจ"),
        {
            "positive": "มีเมนูสำหรับคนที่กินอาหารเฉพาะ",
            "negative": "เมนูสำหรับคนที่กินอาหารเฉพาะอาจมีจำกัด",
            "mixed": "ข้อมูลเรื่องเมนูเฉพาะยังไม่ชัด",
            "neutral": "มีความเห็นเรื่องอาหารเฉพาะ",
        },
        {
            "positive": "หากแพ้อาหารหรือมีข้อจำกัด ควรถามส่วนผสมกับร้านอีกครั้ง",
            "negative": "ควรถามร้านก่อนมา โดยเฉพาะผู้ที่แพ้อาหารหรือมีข้อจำกัด",
            "mixed": "ควรถามเรื่องเมนูและส่วนผสมกับร้านก่อนมา",
            "neutral": "ใช้เป็นข้อมูลเบื้องต้น และถามส่วนผสมกับร้านก่อนสั่ง",
        },
    ),
    _topic(
        "availability",
        "การจองและเวลาเปิดร้าน",
        27,
        ("รับจอง", "จองได้", "โทรจองได้", "มีโต๊ะว่าง", "ยังมีโต๊ะ", "โต๊ะว่าง", "มีที่นั่งว่าง", "ได้โต๊ะทันที", "มีคิวออนไลน์"),
        ("ไม่รับจอง", "จองไม่ได้", "โต๊ะเต็ม", "ร้านปิด", "ปิดร้าน", "ปิดชั่วคราว", "เมนูหมด", "ของหมด", "ขายหมด"),
        ("จองโต๊ะ", "จองคิว", "โทรจอง", "วันหยุดร้าน", "เวลาเปิดร้าน", "เวลาเปิดปิด", "เวลาเปิด-ปิด"),
        {
            "positive": "จองโต๊ะได้หรือมีโต๊ะว่าง",
            "negative": "ควรเช็กโต๊ะหรือเวลาเปิดร้าน",
            "mixed": "โต๊ะ เมนู หรือเวลาเปิดร้านอาจเปลี่ยนได้",
            "neutral": "มีความเห็นเรื่องการจองหรือเวลาเปิดร้าน",
        },
        {
            "positive": "ควรเช็กข้อมูลล่าสุดจากร้านอีกครั้ง",
            "negative": "โทรหรือเช็กกับร้านก่อนออกเดินทาง",
            "mixed": "เช็กโต๊ะ เมนู และเวลาเปิดร้านก่อนมา",
            "neutral": "เช็กข้อมูลล่าสุดจากร้านก่อนมา",
        },
    ),
    _topic(
        "queue",
        "คิวและเวลารอ",
        25,
        ("ไม่ต้องรอ", "รอไม่นาน", "คิวไม่นาน", "คิวเร็ว", "เสิร์ฟเร็ว", "บริการเร็ว", "อาหารมาเร็ว", "รวดเร็ว", "ทันใจ"),
        ("รอนาน", "รอคิวนาน", "คิวยาว", "คิวเยอะ", "คิวแน่น", "เสิร์ฟช้า", "บริการช้า", "อาหารช้า", "อาหารมาช้า", "ช้ามาก"),
        ("รอคิว", "เข้าคิว", "บัตรคิว", "เวลารอ"),
        {
            "positive": "รอไม่นาน",
            "negative": "อาจต้องรอคิว",
            "mixed": "เวลารอของแต่ละคนไม่เหมือนกัน",
            "neutral": "มีความเห็นเรื่องคิว",
        },
        {
            "positive": "ถ้ามีเวลาจำกัด ควรถามคิวล่าสุดกับร้าน",
            "negative": "ถ้ามีเวลาจำกัด ควรเช็กคิวและเผื่อเวลา",
            "mixed": "ควรเช็กคิวล่าสุดและเผื่อเวลาไว้",
            "neutral": "ถ้ามีเวลาจำกัด ควรเช็กคิวก่อนมา",
        },
    ),
    _topic(
        "parking",
        "ที่จอดรถ",
        24,
        ("มีที่จอดรถ", "มีลานจอดรถ", "จอดรถได้", "ที่จอดรถสะดวก", "จอดรถสะดวก", "ที่จอดเยอะ", "ที่จอดกว้าง"),
        ("ไม่มีที่จอดรถ", "หาที่จอดยาก", "ที่จอดรถหายาก", "ที่จอดน้อย", "ที่จอดรถน้อย", "จอดรถยาก", "ที่จอดแคบ", "ที่จอดเต็ม", "จอดเต็ม", "ลานจอดเต็ม", "ต้องจอดริมถนน"),
        ("ที่จอดรถ", "จอดรถ", "ที่จอด", "ลานจอด"),
        {
            "positive": "มีที่จอดรถ",
            "negative": "ที่จอดรถอาจหายาก",
            "mixed": "ความคิดเห็นเรื่องที่จอดรถไม่ตรงกัน",
            "neutral": "มีความเห็นเรื่องที่จอดรถ",
        },
        {
            "positive": "ช่วงคนเยอะที่จอดอาจเต็ม ควรมีจุดจอดสำรอง",
            "negative": "ควรถามร้านหรือหาจุดจอดใกล้ ๆ ก่อนมา",
            "mixed": "ถามร้านและเตรียมจุดจอดสำรองไว้",
            "neutral": "เช็กจุดจอดรถกับร้านก่อนมา",
        },
    ),
    _topic(
        "access",
        "ทางไปร้าน",
        21,
        ("ร้านหาง่าย", "หาร้านง่าย", "ร้านหาไม่ยาก", "หาร้านไม่ยาก", "ทางไปร้านง่าย", "ติดถนนใหญ่", "เดินทางสะดวก", "ใกล้รถไฟฟ้า", "ทางเข้าชัดเจน"),
        ("ร้านหายาก", "หาร้านยาก", "ซอยลึก", "ทางเข้าหายาก", "ทางเข้าแคบ", "เดินทางลำบาก"),
        ("ทางเข้าร้าน", "การเดินทาง", "ติดถนน", "รถไฟฟ้า", "เข้าซอย"),
        {
            "positive": "เดินทางไปที่ร้านได้ง่าย",
            "negative": "ร้านอาจหายาก",
            "mixed": "ความคิดเห็นเรื่องทางไปร้านไม่ตรงกัน",
            "neutral": "มีความเห็นเรื่องทางไปร้าน",
        },
        {
            "positive": "ควรเปิดแผนที่ล่าสุดก่อนมา",
            "negative": "เช็กหมุดและทางเข้าร้านก่อนออกเดินทาง",
            "mixed": "เช็กหมุด และถามทางร้านหากไม่คุ้นพื้นที่",
            "neutral": "เช็กหมุดและทางเข้าร้านก่อนมา",
        },
    ),
    _topic(
        "payment",
        "วิธีจ่ายเงิน",
        20,
        ("รับบัตรเครดิต", "จ่ายบัตรได้", "รับโอน", "โอนได้", "มีพร้อมเพย์", "จ่ายพร้อมเพย์ได้"),
        ("ไม่รับบัตร", "รับเฉพาะเงินสด", "เงินสดเท่านั้น", "โอนไม่ได้", "ไม่รับโอน"),
        ("เงินสด", "บัตรเครดิต", "ชำระเงิน", "พร้อมเพย์", "สแกนจ่าย", "โอนเงิน"),
        {
            "positive": "จ่ายเงินได้หลายช่องทาง",
            "negative": "อาจรับเงินเพียงบางแบบ",
            "mixed": "ความคิดเห็นเรื่องการจ่ายเงินไม่ตรงกัน",
            "neutral": "มีความเห็นเรื่องวิธีจ่ายเงิน",
        },
        {
            "positive": "วิธีจ่ายเงินอาจเปลี่ยนได้ ควรเตรียมวิธีสำรองไว้",
            "negative": "เตรียมเงินสดหรือถามร้านก่อนสั่ง",
            "mixed": "ถามร้านและเตรียมวิธีจ่ายเงินสำรอง",
            "neutral": "เช็กวิธีจ่ายเงินกับร้านอีกครั้ง",
        },
    ),
    _topic(
        "price",
        "ราคา",
        19,
        ("ราคาไม่แพง", "ราคาไม่แรง", "ราคาถูก", "ราคาดี", "ราคาโอเค", "ราคาเหมาะสม", "คุ้มราคา", "คุ้มค่า", "ไม่แพง"),
        ("ราคาแพง", "แพงไป", "ราคาสูง", "ราคาแรง", "ไม่คุ้ม", "ไม่คุ้มค่า", "แพงมาก"),
        ("ราคา", "ค่าอาหาร", "ค่าใช้จ่าย"),
        {
            "positive": "ราคาโดยรวมคุ้มค่า",
            "negative": "ราคาอาจสูงกว่างบ",
            "mixed": "แต่ละคนมองเรื่องราคาไม่เหมือนกัน",
            "neutral": "มีความเห็นเรื่องราคา",
        },
        {
            "positive": "เช็กราคาและเมนูล่าสุดก่อนสั่ง",
            "negative": "ดูราคาในเมนูล่าสุดก่อนตัดสินใจ",
            "mixed": "ควรดูทั้งราคาและปริมาณอาหารจากเมนูล่าสุด",
            "neutral": "เช็กราคาและเมนูล่าสุดจากร้าน",
        },
    ),
    _topic(
        "crowd_noise",
        "คนเยอะและเสียงดัง",
        18,
        ("เงียบสงบ", "คนไม่เยอะ", "ไม่แออัด", "เป็นส่วนตัว"),
        ("คนเยอะ", "คนแน่น", "แออัด", "เสียงดัง", "วุ่นวาย", "คุยกันไม่ได้ยิน"),
        ("ช่วงพีค", "ลูกค้าเยอะ", "เสียงในร้าน"),
        {
            "positive": "ร้านค่อนข้างเงียบ",
            "negative": "ร้านอาจคนเยอะหรือเสียงดัง",
            "mixed": "บรรยากาศอาจต่างกันตามเวลา",
            "neutral": "มีความเห็นเรื่องจำนวนคนหรือเสียงในร้าน",
        },
        {
            "positive": "บรรยากาศอาจเปลี่ยนตามเวลา ควรเช็กคิวถ้าต้องการความสงบ",
            "negative": "ถ้าต้องการความสงบ ควรถามร้านว่าช่วงไหนคนไม่เยอะ",
            "mixed": "เลือกเวลาให้เหมาะกับบรรยากาศที่ต้องการ",
            "neutral": "ถามร้านเรื่องช่วงเวลาที่คนไม่เยอะก่อนมา",
        },
    ),
    _topic(
        "comfort",
        "ที่นั่งและความสบาย",
        16,
        ("แอร์เย็น", "เย็นสบาย", "นั่งสบาย", "ที่นั่งสบาย", "ร้านกว้าง", "กว้างขวาง", "พื้นที่กว้าง", "ไม่อึดอัด"),
        ("แอร์ไม่เย็น", "ร้านร้อน", "ร้อนมาก", "อึดอัด", "คับแคบ", "ที่นั่งน้อย", "โต๊ะเล็ก", "พื้นที่แคบ"),
        ("แอร์", "ที่นั่ง", "พื้นที่ร้าน", "โต๊ะนั่ง"),
        {
            "positive": "ที่นั่งค่อนข้างสบาย",
            "negative": "ที่นั่งอาจไม่สบายสำหรับบางคน",
            "mixed": "ความคิดเห็นเรื่องที่นั่งไม่ตรงกัน",
            "neutral": "มีความเห็นเรื่องที่นั่ง",
        },
        {
            "positive": "ถ้าต้องการที่นั่งแบบเฉพาะ ควรแจ้งร้านล่วงหน้า",
            "negative": "ถ้าให้ความสำคัญกับที่นั่งหรือแอร์ ควรถามร้านก่อนมา",
            "mixed": "ถามร้านเรื่องโซนและที่นั่งก่อนมา",
            "neutral": "ถ้าเรื่องที่นั่งสำคัญ ควรถามร้านก่อนมา",
        },
    ),
    _topic(
        "cleanliness",
        "ความสะอาด",
        17,
        ("ร้านสะอาด", "สะอาดมาก", "ห้องน้ำสะอาด", "โต๊ะสะอาด"),
        ("ร้านสกปรก", "ไม่สะอาด", "ห้องน้ำสกปรก", "ห้องน้ำโทรม", "โต๊ะสกปรก", "โต๊ะเหนียว"),
        ("ความสะอาด", "ห้องน้ำ"),
        {
            "positive": "ร้านได้รับคำชมเรื่องความสะอาด",
            "negative": "มีคนเตือนเรื่องความสะอาด",
            "mixed": "ความคิดเห็นเรื่องความสะอาดไม่ตรงกัน",
            "neutral": "มีความเห็นเรื่องความสะอาด",
        },
        {
            "positive": "ความสะอาดอาจเปลี่ยนได้ ควรดูความคิดเห็นล่าสุดด้วย",
            "negative": "ควรอ่านความคิดเห็นจริงและดูข้อมูลล่าสุดก่อนตัดสินใจ",
            "mixed": "ควรดูความคิดเห็นล่าสุดจากทั้งสองด้าน",
            "neutral": "ควรอ่านความคิดเห็นล่าสุดก่อนตัดสินใจ",
        },
    ),
    _topic(
        "group_accessibility",
        "เหมาะกับใคร",
        15,
        ("เหมาะกับครอบครัว", "เหมาะมาทานกับครอบครัว", "เหมาะมากับครอบครัว", "ร้านประจำของครอบครัว", "พาครอบครัวมาได้", "เหมาะกับเด็ก", "มีเก้าอี้เด็ก", "มีทางลาด", "รถเข็นเข้าได้", "วีลแชร์เข้าได้", "รองรับกลุ่มใหญ่"),
        ("ไม่เหมาะกับเด็ก", "ไม่เหมาะกับผู้สูงอายุ", "ไม่สะดวกสำหรับผู้สูงอายุ", "ผู้สูงอายุไม่สะดวก", "ไม่มีเก้าอี้เด็ก", "ไม่มีทางลาด", "ไม่เหมาะกับรถเข็น", "รถเข็นเข้าไม่ได้", "วีลแชร์เข้าไม่ได้", "ไม่รองรับกลุ่มใหญ่"),
        ("เก้าอี้เด็ก", "ทางลาด", "รถเข็น", "วีลแชร์"),
        {
            "positive": "เหมาะกับครอบครัวหรือกลุ่ม",
            "negative": "อาจไม่สะดวกสำหรับบางกลุ่ม",
            "mixed": "ข้อมูลสำหรับครอบครัวและกลุ่มยังไม่ชัด",
            "neutral": "มีความเห็นเรื่องการมากับครอบครัวหรือกลุ่ม",
        },
        {
            "positive": "ถ้าต้องการที่นั่งหรือสิ่งอำนวยความสะดวก ควรถามร้านก่อน",
            "negative": "แจ้งจำนวนคนและความต้องการกับร้านก่อนมา",
            "mixed": "ถามร้านเรื่องพื้นที่และสิ่งอำนวยความสะดวกก่อนมา",
            "neutral": "ถามร้านให้ตรงกับจำนวนคนและความต้องการของกลุ่ม",
        },
    ),
    _topic(
        "takeaway",
        "ซื้อกลับบ้านและเดลิเวอรี",
        12,
        ("ซื้อกลับได้", "ซื้อกลับบ้าน", "สั่งกลับบ้าน", "สั่งกลับบ้านได้", "มีเดลิเวอรี", "มีเดลิเวอรี่", "ส่งอาหารได้"),
        ("ซื้อกลับไม่ได้", "ไม่มีเดลิเวอรี", "ไม่มีเดลิเวอรี่", "ไม่ส่งอาหาร"),
        ("ซื้อกลับบ้าน", "สั่งกลับบ้าน", "เดลิเวอรี", "เดลิเวอรี่", "ส่งอาหาร"),
        {
            "positive": "สั่งกลับบ้านหรือเดลิเวอรีได้",
            "negative": "การสั่งกลับบ้านหรือเดลิเวอรีอาจมีข้อจำกัด",
            "mixed": "ข้อมูลเรื่องซื้อกลับและเดลิเวอรียังไม่ชัด",
            "neutral": "มีความเห็นเรื่องซื้อกลับหรือเดลิเวอรี",
        },
        {
            "positive": "เช็กช่องทางสั่งและพื้นที่จัดส่งล่าสุดกับร้าน",
            "negative": "ถ้าจะไม่กินที่ร้าน ควรถามร้านก่อนมา",
            "mixed": "เช็กช่องทางสั่งและเงื่อนไขล่าสุดกับร้าน",
            "neutral": "เช็กช่องทางสั่งล่าสุดจากร้าน",
        },
    ),
)


# A practical topic may feed both consumer planning and the operator view.
# Keep the mapping here so every presentation layer classifies a topic in the
# same way instead of maintaining its own copy of the rules.
TOPIC_ASPECTS = {
    "dietary": "food",
    "availability": "service",
    "queue": "service",
    "parking": "ambience",
    "access": "ambience",
    "payment": "service",
    "price": "food",
    "crowd_noise": "ambience",
    "comfort": "ambience",
    "cleanliness": "ambience",
    "group_accessibility": "ambience",
    "takeaway": "service",
}


_CONTEXT_CUES = (
    "ช่วงเช้า", "ช่วงเที่ยง", "ช่วงบ่าย", "ช่วงเย็น", "ช่วงค่ำ", "ช่วงดึก",
    "ตอนเช้า", "ตอนเที่ยง", "ตอนเย็น", "กลางคืน", "วันธรรมดา", "วันหยุด",
    "วันเสาร์", "วันอาทิตย์", "เสาร์อาทิตย์", "ช่วงพีค",
)


_STATUS_PRESENTATION = {
    "negative": {
        "action_tier": "plan",
        "status_label": "ควรวางแผน",
    },
    "mixed": {
        "action_tier": "plan",
        "status_label": "ข้อมูลไม่ตรงกัน",
    },
    "neutral": {
        "action_tier": "check",
        "status_label": "ควรเช็กเพิ่ม",
    },
    "positive": {
        "action_tier": "ready",
        "status_label": "ข้อมูลที่เป็นประโยชน์",
    },
}


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "").lower())


def _matched_cues(text: str, cues: tuple[str, ...]) -> list[str]:
    compact = _compact(text)
    return [cue for cue in cues if _compact(cue) in compact]


def _remove_opposite_substrings(
    positive: list[str], negative: list[str]
) -> tuple[list[str], list[str]]:
    """Prevent 'ไม่แพง' from also matching 'แพง', and similar overlaps."""
    pos = [p for p in positive if not any(_compact(p) in _compact(n) and len(_compact(n)) > len(_compact(p)) for n in negative)]
    neg = [n for n in negative if not any(_compact(n) in _compact(p) and len(_compact(p)) > len(_compact(n)) for p in positive)]
    return pos, neg


def _polarity(
    topic: dict,
    text: str,
) -> tuple[str | None, list[str]]:
    positive = _matched_cues(text, topic["positive"])
    negative = _matched_cues(text, topic["negative"])
    positive, negative = _remove_opposite_substrings(positive, negative)
    factual = _matched_cues(text, topic["factual"])
    matches = sorted(set(positive + negative + factual), key=lambda cue: (-len(cue), cue))
    if not matches:
        return None, []
    if positive and negative:
        return "mixed", matches
    if negative:
        return "negative", matches
    if positive:
        return "positive", matches
    # A factual mention is not an opinion.  In particular, do not inherit the
    # sentiment of an extracted phrase: "พนักงานบอกที่จอดรถให้ดีมาก" praises
    # service but does not prove that the restaurant has convenient parking.
    return "neutral", matches


def match_topic(text: str) -> str | None:
    """Return the first practical topic explicitly supported by ``text``."""
    for topic in PRACTICAL_TOPICS:
        polarity, _ = _polarity(topic, text)
        if polarity is not None:
            return topic["key"]
    return None


def _evidence_label(review_count: int) -> tuple[str, str]:
    # Product heuristic, deliberately not described as statistical confidence.
    if review_count <= 1:
        return "preliminary", "พูดถึง 1 ครั้ง"
    if review_count <= 3:
        return "repeated", "พูดถึงหลายครั้ง"
    return "frequent", "ถูกพูดถึงบ่อย"


def _status_for(evidence: dict[str, list[str]]) -> str:
    if evidence["mixed"] or (evidence["positive"] and evidence["negative"]):
        return "mixed"
    if evidence["negative"]:
        return "negative"
    if evidence["positive"]:
        return "positive"
    return "neutral"


def _summary(topic: dict, status: str, evidence: dict[str, list[str]], total: int) -> str:
    positive = len(set(evidence["positive"]))
    negative = len(set(evidence["negative"]))
    if status == "mixed":
        if positive and negative:
            return f"พบความคิดเห็นเชิงบวก {positive} ความเห็น และเชิงลบ {negative} ความเห็น จากทั้งหมด {total} ความเห็นในเรื่องนี้"
        return f"มี {total} ความคิดเห็นที่พูดถึงทั้งข้อดีและข้อจำกัดในเรื่องเดียวกัน"
    if status == "positive":
        return f"พบข้อมูลในทางบวกจาก {total} ความคิดเห็นเรื่อง{topic['label']}"
    if status == "negative":
        return f"พบข้อจำกัดจาก {total} ความคิดเห็นเรื่อง{topic['label']}"
    return f"มี {total} ความคิดเห็นในเรื่องนี้ แต่ยังสรุปทิศทางไม่ได้ชัดเจน"


def _context_text(contexts: list[str]) -> str:
    if not contexts:
        return ""
    if len(contexts) == 1:
        return f"มีผู้พูดถึงใน{contexts[0]}"
    return f"มีผู้พูดถึงใน{contexts[0]}และ{contexts[1]}"


def build_practical_insights(
    reviews: list[dict] | None,
    phrase_items: list[dict] | None = None,
    limit: int = 6,
) -> list[dict]:
    """Group traceable review evidence into practical restaurant topics."""
    reviews = reviews or []
    phrase_items = phrase_items or []
    results = []

    for topic_index, topic in enumerate(PRACTICAL_TOPICS):
        evidence = {key: [] for key in ("positive", "neutral", "negative", "mixed")}
        query_counts: Counter[str] = Counter()
        context_counts: Counter[str] = Counter()

        for index, review in enumerate(reviews):
            review_id = str(review.get("review_id") or f"R{index + 1:03d}")
            polarity, matches = _polarity(topic, review.get("text", ""))
            if polarity is None:
                continue
            evidence[polarity].append(review_id)
            query_counts.update(matches)
            context_counts.update(_matched_cues(review.get("text", ""), _CONTEXT_CUES))

        # Phrase evidence preserves support for legacy results and helps when a
        # phrase extractor retained a practical cue that review text is absent.
        for item in phrase_items:
            polarity, matches = _polarity(
                topic,
                item.get("text", ""),
            )
            if polarity is None:
                continue
            ids = [str(value) for value in item.get("evidence_review_ids", []) if value]
            evidence[polarity].extend(ids)
            query_counts.update({cue: max(1, len(ids)) for cue in matches})

        for key in evidence:
            evidence[key] = list(dict.fromkeys(evidence[key]))
        all_ids = list(dict.fromkeys(
            review_id
            for key in ("positive", "neutral", "negative", "mixed")
            for review_id in evidence[key]
        ))
        if not all_ids:
            continue

        status = _status_for(evidence)
        evidence_level, evidence_label = _evidence_label(len(all_ids))
        presentation = _STATUS_PRESENTATION[status]
        query = query_counts.most_common(1)[0][0] if query_counts else topic["label"]
        contexts = [cue for cue, _ in context_counts.most_common(2)]
        status_weight = {"negative": 8, "mixed": 7, "neutral": 2, "positive": 0}[status]
        score = len(all_ids) * 10 + topic["decision_weight"] + status_weight
        results.append({
            "topic": topic["key"],
            "topic_label": topic["label"],
            "aspect": TOPIC_ASPECTS[topic["key"]],
            "status": status,
            "sentiment": "neutral" if status == "mixed" else status,
            "title": topic["titles"][status],
            "text": topic["titles"][status],
            "summary": _summary(topic, status, evidence, len(all_ids)),
            "advice": topic["advice"][status],
            "review_count": len(all_ids),
            "count": len(all_ids),
            "evidence_level": evidence_level,
            "evidence_label": evidence_label,
            "action_tier": presentation["action_tier"],
            "status_label": presentation["status_label"],
            "evidence_review_ids": all_ids,
            "positive_review_count": len(set(evidence["positive"])),
            "negative_review_count": len(set(evidence["negative"])),
            "neutral_review_count": len(set(evidence["neutral"])),
            "context_labels": contexts,
            "context_text": _context_text(contexts),
            "query": query,
            "aspect_th": topic["label"],
            "_score": score,
            "_topic_index": topic_index,
        })

    results.sort(key=lambda item: (-item["_score"], item["_topic_index"]))
    for rank, item in enumerate(results, start=1):
        item.pop("_score", None)
        item.pop("_topic_index", None)
        item["rank"] = rank
    return results[:max(0, limit)]


def enrich_result(result: dict, limit: int = 6) -> dict:
    """Attach the deterministic before-you-go view to an analysis payload.

    This adapter keeps the original rule engine independent from Flask and the
    database.  It also gives every persisted review a stable evidence ID so a
    displayed planning topic can always be traced back to its source reviews.
    """
    reviews = result.get("reviews") or []
    for index, review in enumerate(reviews):
        review.setdefault("review_id", f"R{index + 1:03d}")

    phrase_items = []
    for buckets in (result.get("keywords") or {}).values():
        for phrases in (buckets or {}).values():
            for phrase in phrases or []:
                phrase_items.append({
                    "text": str(phrase.get("word") or "").strip(),
                    "evidence_review_ids": list(dict.fromkeys(
                        phrase.get("evidence_review_ids") or []
                    )),
                })

    items = build_practical_insights(
        reviews=reviews,
        phrase_items=phrase_items,
        limit=limit,
    )
    evidence_review_ids = list(dict.fromkeys(
        review_id
        for item in items
        for review_id in item.get("evidence_review_ids", [])
    ))
    result["practical_insights"] = items
    result["practical_insights_meta"] = {
        "topic_count": len(items),
        "evidence_review_count": len(evidence_review_ids),
        "attention_count": sum(
            item.get("action_tier") == "plan" for item in items
        ),
        "repeated_count": sum(
            int(item.get("review_count") or 0) >= 2 for item in items
        ),
    }
    return result
