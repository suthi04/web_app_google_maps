"""
database.py
===========
ชั้นฐานข้อมูล SQLite — เก็บผลวิเคราะห์เพื่อทำ History และ Save (รายการโปรด)

ออกแบบตาราง (ตาม B9 ในแผน):
- analysis : 1 แถว = 1 ครั้งที่วิเคราะห์ (เก็บผลรวมเป็น JSON ใน payload เพื่อความง่ายในเฟส 1)
             Phase 2 ค่อยแตกตาราง review/keyword แยกถ้าต้องการ query ละเอียด

ฟังก์ชันหลัก:
  init_db()                       สร้างตาราง
  save_analysis(result)           บันทึกผล -> คืน id
  list_analyses()                 รายการประวัติ (สำหรับหน้า History)
  get_analysis(aid)               ดึงผลเต็มกลับมา
  toggle_saved(aid)               สลับสถานะรายการโปรด
  list_saved()                    รายการที่ถูกบันทึก
"""
import json
import os
import sqlite3
from datetime import datetime

import config

_DB_PATH = os.path.join(config.BASE_DIR, "insightreview.db")


def _conn():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS analysis (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                store_name    TEXT,
                source_url    TEXT,
                analyzed_at   TEXT,
                total_reviews INTEGER,
                pct_positive  INTEGER,
                pct_neutral   INTEGER,
                pct_negative  INTEGER,
                is_saved      INTEGER DEFAULT 0,
                payload       TEXT
            )
        """)


def save_analysis(result: dict) -> int:
    pct = result["distribution"]["pct"]
    with _conn() as c:
        cur = c.execute(
            """INSERT INTO analysis
               (store_name, source_url, analyzed_at, total_reviews,
                pct_positive, pct_neutral, pct_negative, payload)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                result["store_name"],
                result["source_url"],
                datetime.now().isoformat(timespec="seconds"),
                result["total_reviews"],
                pct["positive"], pct["neutral"], pct["negative"],
                json.dumps(result, ensure_ascii=False),
            ),
        )
        return cur.lastrowid


def list_analyses(limit: int = 50) -> list:
    with _conn() as c:
        rows = c.execute(
            """SELECT id, store_name, source_url, analyzed_at, total_reviews,
                      pct_positive, pct_neutral, pct_negative, is_saved
               FROM analysis ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_analysis(aid: int) -> dict | None:
    with _conn() as c:
        row = c.execute(
            "SELECT payload, is_saved FROM analysis WHERE id = ?", (aid,)
        ).fetchone()
        if not row:
            return None
        data = json.loads(row["payload"])
        data["id"] = aid
        data["is_saved"] = bool(row["is_saved"])
        return data


def toggle_saved(aid: int) -> bool:
    with _conn() as c:
        row = c.execute(
            "SELECT is_saved FROM analysis WHERE id = ?", (aid,)
        ).fetchone()
        if not row:
            return False
        new_val = 0 if row["is_saved"] else 1
        c.execute("UPDATE analysis SET is_saved = ? WHERE id = ?", (new_val, aid))
        return bool(new_val)


def list_saved(limit: int = 50) -> list:
    with _conn() as c:
        rows = c.execute(
            """SELECT id, store_name, source_url, analyzed_at, total_reviews,
                      pct_positive, pct_neutral, pct_negative, is_saved
               FROM analysis WHERE is_saved = 1 ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_analysis(aid: int) -> bool:
    """ลบผลวิเคราะห์ 1 รายการ (ใช้กับปุ่มลบในหน้า History)"""
    with _conn() as c:
        cur = c.execute("DELETE FROM analysis WHERE id = ?", (aid,))
        return cur.rowcount > 0
