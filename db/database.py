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
import logging
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta

import config

_DB_PATH = os.path.join(config.BASE_DIR, "insightreview.db")
log = logging.getLogger(__name__)
_JOB_STAGES = {
    "queued", "fetching_reviews", "preprocessing", "sentiment", "aspects",
    "phrases", "insights", "finalizing", "completed", "failed",
}


@contextmanager
def _conn():
    conn = sqlite3.connect(_DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


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
                owner_id      TEXT,
                payload       TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS analysis_job (
                id            TEXT PRIMARY KEY,
                status        TEXT NOT NULL,
                source_url    TEXT,
                created_at    TEXT NOT NULL,
                started_at    TEXT,
                finished_at   TEXT,
                analysis_id   INTEGER,
                error_message TEXT,
                owner_id      TEXT,
                stage         TEXT NOT NULL DEFAULT 'queued',
                progress      INTEGER NOT NULL DEFAULT 0,
                CHECK (status IN ('queued', 'running', 'completed', 'failed'))
            )
        """)
        # Additive migrations preserve old results without exposing them to a
        # newly-created anonymous browser identity. Legacy rows keep owner_id
        # NULL and therefore match no public request.
        analysis_columns = {
            row["name"] for row in c.execute("PRAGMA table_info(analysis)")
        }
        if "owner_id" not in analysis_columns:
            c.execute("ALTER TABLE analysis ADD COLUMN owner_id TEXT")

        job_columns = {
            row["name"] for row in c.execute("PRAGMA table_info(analysis_job)")
        }
        if "stage" not in job_columns:
            c.execute(
                "ALTER TABLE analysis_job ADD COLUMN stage TEXT NOT NULL DEFAULT 'queued'"
            )
        if "progress" not in job_columns:
            c.execute(
                "ALTER TABLE analysis_job ADD COLUMN progress INTEGER NOT NULL DEFAULT 0"
            )
        if "owner_id" not in job_columns:
            c.execute("ALTER TABLE analysis_job ADD COLUMN owner_id TEXT")

        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_analysis_owner_id "
            "ON analysis(owner_id, id DESC)"
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_analysis_owner_saved "
            "ON analysis(owner_id, is_saved, id DESC)"
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_analysis_job_owner_id "
            "ON analysis_job(owner_id, id)"
        )


def healthcheck() -> bool:
    """Verify that SQLite can accept a query; intended for service probes."""
    with _conn() as c:
        return c.execute("SELECT 1").fetchone()[0] == 1


def _require_owner_id(owner_id: str) -> str:
    if not isinstance(owner_id, str) or not owner_id:
        raise ValueError("owner_id is required")
    return owner_id


def create_job(source_url: str, owner_id: str) -> str:
    """Persist a queued analysis job and return an unguessable public id."""
    job_id = uuid.uuid4().hex
    with _conn() as c:
        c.execute(
            """INSERT INTO analysis_job
               (id, status, source_url, created_at, owner_id, stage, progress)
               VALUES (?, 'queued', ?, ?, ?, 'queued', 0)""",
            (
                job_id, source_url, datetime.now().isoformat(timespec="seconds"),
                _require_owner_id(owner_id),
            ),
        )
    return job_id


def get_job(job_id: str, owner_id: str) -> dict | None:
    with _conn() as c:
        row = c.execute(
            """SELECT id, status, created_at, started_at, finished_at,
                      analysis_id, error_message, stage, progress
               FROM analysis_job WHERE id = ? AND owner_id = ?""",
            (job_id, _require_owner_id(owner_id)),
        ).fetchone()
        return dict(row) if row else None


def mark_job_running(job_id: str) -> bool:
    with _conn() as c:
        cur = c.execute(
            """UPDATE analysis_job
               SET status = 'running', stage = 'fetching_reviews', progress = 5,
                   started_at = ?
               WHERE id = ? AND status = 'queued'""",
            (datetime.now().isoformat(timespec="seconds"), job_id),
        )
        return cur.rowcount == 1


def update_job_progress(job_id: str, stage: str, progress: int) -> bool:
    if stage not in _JOB_STAGES:
        raise ValueError(f"Unknown analysis job stage: {stage}")
    progress = max(0, min(99, int(progress)))
    with _conn() as c:
        cur = c.execute(
            """UPDATE analysis_job SET stage = ?, progress = ?
               WHERE id = ? AND status = 'running'""",
            (stage, progress, job_id),
        )
        return cur.rowcount == 1


def mark_job_completed(job_id: str, analysis_id: int) -> bool:
    with _conn() as c:
        cur = c.execute(
            """UPDATE analysis_job
               SET status = 'completed', stage = 'completed', progress = 100,
                   analysis_id = ?, finished_at = ?,
                   error_message = NULL
               WHERE id = ? AND status = 'running'
                 AND EXISTS (
                     SELECT 1 FROM analysis
                     WHERE analysis.id = ?
                       AND analysis.owner_id = analysis_job.owner_id
                 )""",
            (
                analysis_id, datetime.now().isoformat(timespec="seconds"),
                job_id, analysis_id,
            ),
        )
        return cur.rowcount == 1


def mark_job_failed(job_id: str, message: str) -> bool:
    with _conn() as c:
        cur = c.execute(
            """UPDATE analysis_job
               SET status = 'failed', stage = 'failed', error_message = ?,
                   finished_at = ?
               WHERE id = ? AND status IN ('queued', 'running')""",
            (message[:500], datetime.now().isoformat(timespec="seconds"), job_id),
        )
        return cur.rowcount == 1


def delete_job(job_id: str) -> bool:
    with _conn() as c:
        cur = c.execute("DELETE FROM analysis_job WHERE id = ?", (job_id,))
        return cur.rowcount == 1


def recover_interrupted_jobs() -> int:
    """Fail jobs lost by a previous process restart instead of leaving them stuck."""
    with _conn() as c:
        cur = c.execute(
            """UPDATE analysis_job
               SET status = 'failed',
                   stage = 'failed',
                   error_message = 'งานหยุดลงเนื่องจากระบบเริ่มทำงานใหม่ กรุณาลองอีกครั้ง',
                   finished_at = ?
               WHERE status IN ('queued', 'running')""",
            (datetime.now().isoformat(timespec="seconds"),),
        )
        return cur.rowcount


def prune_finished_jobs(retention_days: int = 7) -> int:
    """Delete old job metadata; completed analyses themselves are preserved."""
    cutoff = datetime.now() - timedelta(days=max(1, retention_days))
    with _conn() as c:
        cur = c.execute(
            """DELETE FROM analysis_job
               WHERE status IN ('completed', 'failed')
                 AND finished_at IS NOT NULL AND finished_at < ?""",
            (cutoff.isoformat(timespec="seconds"),),
        )
        return cur.rowcount


def save_analysis(result: dict, owner_id: str) -> int:
    pct = result["distribution"]["pct"]
    with _conn() as c:
        cur = c.execute(
            """INSERT INTO analysis
               (store_name, source_url, analyzed_at, total_reviews,
                pct_positive, pct_neutral, pct_negative, owner_id, payload)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                result["store_name"],
                result["source_url"],
                datetime.now().isoformat(timespec="seconds"),
                result["total_reviews"],
                pct["positive"], pct["neutral"], pct["negative"],
                _require_owner_id(owner_id),
                json.dumps(result, ensure_ascii=False),
            ),
        )
        return cur.lastrowid


def list_analyses(owner_id: str, limit: int = 50) -> list:
    with _conn() as c:
        rows = c.execute(
            """SELECT id, store_name, source_url, analyzed_at, total_reviews,
                      pct_positive, pct_neutral, pct_negative, is_saved
               FROM analysis WHERE owner_id = ? ORDER BY id DESC LIMIT ?""",
            (_require_owner_id(owner_id), limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_analysis(aid: int, owner_id: str) -> dict | None:
    with _conn() as c:
        row = c.execute(
            "SELECT payload, is_saved FROM analysis WHERE id = ? AND owner_id = ?",
            (aid, _require_owner_id(owner_id)),
        ).fetchone()
        if not row:
            return None
        try:
            data = json.loads(row["payload"])
        except (json.JSONDecodeError, TypeError):
            log.exception("Invalid JSON payload for analysis id=%s", aid)
            raise
        data["id"] = aid
        data["is_saved"] = bool(row["is_saved"])
        return data


def toggle_saved(aid: int, owner_id: str) -> bool | None:
    with _conn() as c:
        row = c.execute(
            "SELECT is_saved FROM analysis WHERE id = ? AND owner_id = ?",
            (aid, _require_owner_id(owner_id)),
        ).fetchone()
        if not row:
            return None
        new_val = 0 if row["is_saved"] else 1
        c.execute(
            "UPDATE analysis SET is_saved = ? WHERE id = ? AND owner_id = ?",
            (new_val, aid, owner_id),
        )
        return bool(new_val)


def list_saved(owner_id: str, limit: int = 50) -> list:
    with _conn() as c:
        rows = c.execute(
            """SELECT id, store_name, source_url, analyzed_at, total_reviews,
                      pct_positive, pct_neutral, pct_negative, is_saved
               FROM analysis WHERE owner_id = ? AND is_saved = 1
               ORDER BY id DESC LIMIT ?""",
            (_require_owner_id(owner_id), limit),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_analysis(aid: int, owner_id: str) -> bool:
    """ลบผลวิเคราะห์ 1 รายการ (ใช้กับปุ่มลบในหน้า History)"""
    with _conn() as c:
        cur = c.execute(
            "DELETE FROM analysis WHERE id = ? AND owner_id = ?",
            (aid, _require_owner_id(owner_id)),
        )
        return cur.rowcount > 0


def delete_all_analyses(owner_id: str) -> int:
    """ลบผลวิเคราะห์ของเบราว์เซอร์ปัจจุบันและคืนจำนวนรายการที่ถูกลบ"""
    with _conn() as c:
        cur = c.execute(
            "DELETE FROM analysis WHERE owner_id = ?",
            (_require_owner_id(owner_id),),
        )
        return cur.rowcount
