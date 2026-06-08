"""
export.py
=========
สร้างไฟล์ส่งออกจากผลวิเคราะห์ เพื่อใช้ในงานวิจัย:
  - reviews_csv()   : รีวิวรายรายการ + อารมณ์ที่ทำนาย + หมวด  (ใส่ภาคผนวก/ตรวจสอบเอง)
  - summary_csv()   : สถิติสรุป (สัดส่วนอารมณ์ + อารมณ์ราย aspect)
  - labeling_json() : รีวิวล้วน ๆ สำหรับนำไปติด label ด้วย eval/label_tool.py
                      (เพื่อสร้างชุดทดสอบ ~400 รายการจากข้อมูลจริง แล้ววัด F1)

หมายเหตุ: CSV เขียนด้วย BOM (\\ufeff) เพื่อให้ Excel บน Windows เปิดภาษาไทยไม่เพี้ยน
"""
import csv
import io
import json

_SENT_TH = {"positive": "บวก", "neutral": "กลาง", "negative": "ลบ"}
_ASPECT_TH = {"food": "อาหาร", "service": "บริการ",
              "ambience": "บรรยากาศ", "uncategorized": "อื่น ๆ"}


def _to_csv(header: list, rows: list) -> str:
    buf = io.StringIO()
    buf.write("\ufeff")                 # BOM ให้ Excel อ่านไทยถูก
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue()


def reviews_csv(a: dict) -> str:
    """ตารางรีวิวรายรายการ"""
    header = ["ลำดับ", "รีวิว", "คะแนนดาว", "วันที่", "อารมณ์ (ทำนาย)", "หมวดที่กล่าวถึง"]
    rows = []
    for i, r in enumerate(a.get("reviews", []), 1):
        aspects = ", ".join(_ASPECT_TH.get(x, x) for x in r.get("aspects", []))
        rows.append([
            i,
            r.get("text", ""),
            r.get("rating") or "",
            r.get("review_date") or "",
            _SENT_TH.get(r.get("sentiment"), r.get("sentiment", "")),
            aspects,
        ])
    return _to_csv(header, rows)


def summary_csv(a: dict) -> str:
    """สถิติสรุปของร้าน"""
    dist = a.get("distribution", {})
    pct = dist.get("pct", {})
    cnt = dist.get("counts", {})

    rows = [
        ["ร้าน", a.get("store_name", "")],
        ["จำนวนรีวิวที่วิเคราะห์", a.get("total_reviews", 0)],
        ["เครื่องมือวิเคราะห์", a.get("engine", "")],
        ["", ""],
        ["อารมณ์", "จำนวน", "เปอร์เซ็นต์"],
        ["บวก", cnt.get("positive", 0), f"{pct.get('positive', 0)}%"],
        ["กลาง", cnt.get("neutral", 0), f"{pct.get('neutral', 0)}%"],
        ["ลบ", cnt.get("negative", 0), f"{pct.get('negative', 0)}%"],
        ["", ""],
        ["หมวด", "บวก", "กลาง", "ลบ", "รวม"],
    ]
    for aspect, s in a.get("aspect_summary", {}).items():
        rows.append([
            _ASPECT_TH.get(aspect, aspect),
            s.get("positive", 0), s.get("neutral", 0),
            s.get("negative", 0), s.get("total", 0),
        ])

    rows.append(["", ""])
    rows.append(["ข้อสรุปเชิงปฏิบัติ", ""])
    for ins in a.get("insights", []):
        rows.append([ins.get("aspect_th", ""), ins.get("message", "")])

    # ใช้ writer ตรง ๆ เพราะจำนวนคอลัมน์ไม่เท่ากัน
    buf = io.StringIO()
    buf.write("\ufeff")
    w = csv.writer(buf)
    for row in rows:
        w.writerow(row)
    return buf.getvalue()


def labeling_json(a: dict) -> str:
    """รีวิวล้วน ๆ สำหรับนำไปติด label (กินกับ eval/label_tool.py)"""
    payload = {
        "_comment": f"รีวิวจริงจาก '{a.get('store_name','')}' — นำไปติด label ด้วย eval/label_tool.py",
        "reviews": [{"text": r.get("text", "")} for r in a.get("reviews", [])],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
