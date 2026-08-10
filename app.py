"""
app.py
======
Flask application — จุดเข้าของเว็บทั้งหมด

Routes:
  GET  /                 หน้าแรก (ช่องวาง URL + ปุ่ม Analyze)
  POST /analyze          รับ URL -> เข้าคิว background -> redirect ไปหน้าสถานะงาน
  GET  /dashboard/<id>   หน้าแสดงผลวิเคราะห์
  GET  /history          ประวัติการวิเคราะห์
  GET  /saved            รายการโปรด
  POST /toggle-save/<id> สลับสถานะรายการโปรด
  POST /delete/<id>      ลบผลวิเคราะห์
  POST /delete-all       ลบผลวิเคราะห์ทั้งหมด
  GET  /api/analysis/<id> คืนผลเป็น JSON

หมายเหตุ: ทุก route ที่อาจล้มเหลว (โดยเฉพาะ /analyze ที่เรียก Apify/โมเดล)
ถูกครอบด้วย error handling เพื่อไม่ให้ผู้ใช้เจอหน้า 500 ดิบ ๆ
"""
import logging
from urllib.parse import parse_qs, urlparse

from flask import (
    Flask, render_template, request, redirect, url_for, jsonify, abort, flash,
    Response,
)

import config
from background_jobs import BackgroundJobRunner
from core import pipeline, export, audience_insights, insights
from db import database
from request_limits import SlidingWindowRateLimiter
from web_security import add_security_headers, csrf_token, protect_csrf

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config.update(
    MAX_CONTENT_LENGTH=1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=config.SESSION_COOKIE_SECURE,
)
database.init_db()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("insightreview")
recovered_jobs = database.recover_interrupted_jobs()
if recovered_jobs:
    log.warning("Marked %s interrupted analysis jobs as failed", recovered_jobs)
database.prune_finished_jobs(config.JOB_RETENTION_DAYS)

analysis_limiter = SlidingWindowRateLimiter(
    max_requests=config.ANALYZE_MAX_REQUESTS,
    window_seconds=config.ANALYZE_WINDOW_SECONDS,
)
job_runner = BackgroundJobRunner(
    pipeline.run_analysis,
    database,
    max_workers=config.ANALYZE_MAX_CONCURRENT,
    max_queued=config.ANALYZE_MAX_QUEUED,
)

app.before_request(protect_csrf)
app.after_request(add_security_headers)


@app.context_processor
def inject_globals():
    return {
        "demo_mode": not config.get_apify_token(),
        "csrf_token": csrf_token(),
        "analysis_defaults": config.get_settings(),
        "min_reviews": config.MIN_REVIEWS,
        "max_reviews_cap": config.MAX_REVIEWS_CAP,
        # Bump when shared CSS/JS changes so long-lived browser caches refresh.
        "asset_version": "20260810-delete-all1",
    }


def _looks_like_maps_url(url: str) -> bool:
    """ตรวจว่า URL ชี้ไปยัง Google Maps host/path ที่รองรับจริง

    ห้ามตรวจด้วย substring อย่างเดียว เพราะ URL เช่น ``evil.com/?cid=1`` หรือ
    ``maps.google.com.evil.com`` สามารถผ่านได้และทำให้เสีย Apify quota โดยเปล่าประโยชน์
    """
    try:
        parsed = urlparse((url or "").strip())
    except ValueError:
        return False

    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False

    host = parsed.hostname.lower().rstrip(".")
    path = parsed.path.lower()

    if host == "maps.app.goo.gl":
        return bool(path and path != "/")
    if host == "goo.gl":
        return path.startswith("/maps/")

    is_google = (
        host in {"google.com", "google.co.th"}
        or host.endswith(".google.com")
        or host.endswith(".google.co.th")
    )
    if not is_google:
        return False

    # maps.google.* เป็น host สำหรับ Maps โดยตรง ส่วน google.* ต้องมี /maps หรือ cid
    if host.startswith("maps."):
        return True
    return (
        path == "/maps"
        or path.startswith("/maps/")
        or "cid" in parse_qs(parsed.query, keep_blank_values=True)
    )


@app.route("/")
def index():
    return render_template("index.html")


def _analysis_unavailable(status: int, title: str, message: str, retry_after: int):
    return (
        render_template(
            "error.html", code=str(status), title=title, message=message
        ),
        status,
        {"Retry-After": str(max(1, retry_after))},
    )


def _analysis_options_from_form() -> dict:
    """Validate per-job analysis choices without mutating shared settings."""
    defaults = config.get_settings()
    sentiment_engine = request.form.get("engine")
    if sentiment_engine not in {"model", "lexicon"}:
        sentiment_engine = "model" if defaults["use_model"] else "lexicon"

    extract_engine = request.form.get("extract_engine")
    if extract_engine not in {"rule", "llm"}:
        extract_engine = defaults["extract_engine"]

    try:
        max_reviews = int(request.form.get("max_reviews", defaults["max_reviews"]))
    except (TypeError, ValueError, OverflowError):
        max_reviews = defaults["max_reviews"]
    max_reviews = max(config.MIN_REVIEWS, min(config.MAX_REVIEWS_CAP, max_reviews))
    return {
        "use_model": sentiment_engine == "model",
        "extract_engine": extract_engine,
        "max_reviews": max_reviews,
    }


@app.route("/analyze", methods=["POST"])
def analyze():
    url = (request.form.get("url") or "").strip()
    analysis_options = _analysis_options_from_form()

    if len(url) > 2048:
        flash("ลิงก์ยาวเกินไป กรุณาใช้ลิงก์ Google Maps โดยตรง", "err")
        return redirect(url_for("index"))

    # โหมดจริง (มี Apify token): ต้องมี URL และต้องเป็นลิงก์ Maps
    if config.get_apify_token():
        if not url:
            flash("กรุณาวางลิงก์ร้านจาก Google Maps ก่อนเริ่มวิเคราะห์", "err")
            return redirect(url_for("index"))
        if not _looks_like_maps_url(url):
            flash("ลิงก์ไม่ถูกต้อง — ใช้ลิงก์ร้านอาหารจาก Google Maps เท่านั้น", "err")
            return redirect(url_for("index"))

    if not job_runner.reserve():
        return _analysis_unavailable(
            503,
            "คิววิเคราะห์เต็ม",
            "มีงานกำลังรอหรือประมวลผลครบจำนวนแล้ว กรุณารอสักครู่ก่อนส่งรายการใหม่",
            5,
        )

    allowed, retry_after = analysis_limiter.consume(request.remote_addr or "unknown")
    if not allowed:
        job_runner.cancel_reservation()
        return _analysis_unavailable(
            429,
            "วิเคราะห์บ่อยเกินไป",
            "กรุณารอตามเวลาที่กำหนดแล้วจึงเริ่มวิเคราะห์รายการใหม่",
            retry_after,
        )

    try:
        job_id = database.create_job(url)
    except Exception as e:  # noqa: BLE001 - release reserved queue capacity
        job_runner.cancel_reservation()
        log.exception("Could not create analysis job: %s", e)
        flash("สร้างงานวิเคราะห์ไม่สำเร็จ กรุณาลองใหม่", "err")
        return redirect(url_for("index"))

    if not job_runner.submit_reserved(job_id, url, analysis_options):
        database.delete_job(job_id)
        return _analysis_unavailable(
            503, "เริ่มตัวประมวลผลไม่สำเร็จ", "กรุณารอสักครู่แล้วลองใหม่", 5
        )
    return redirect(url_for("job_status", job_id=job_id))


@app.route("/jobs/<job_id>")
def job_status(job_id):
    job = database.get_job(job_id)
    if not job:
        abort(404)
    if job["status"] == "completed" and job.get("analysis_id"):
        return redirect(url_for("dashboard", aid=job["analysis_id"]))
    return render_template("job.html", job=job)


@app.route("/api/jobs/<job_id>")
def api_job_status(job_id):
    job = database.get_job(job_id)
    if not job:
        abort(404)
    payload = dict(job)
    if job["status"] == "completed" and job.get("analysis_id"):
        payload["dashboard_url"] = url_for(
            "dashboard", aid=job["analysis_id"]
        )
    return jsonify(payload)


def _aspect_examples(data: dict, per_bucket: int = 3, max_len: int = 220) -> dict:
    """Collect traceable review excerpts for each aspect and sentiment."""
    examples = {}
    reviews = data.get("reviews") or []
    for aspect in (data.get("aspect_summary") or {}):
        buckets = {"positive": [], "neutral": [], "negative": []}
        for review in reviews:
            sentiment = review.get("sentiment")
            if (
                aspect in (review.get("aspects") or [])
                and sentiment in buckets
                and len(buckets[sentiment]) < per_bucket
            ):
                text = str(review.get("text") or "").strip()
                if text:
                    buckets[sentiment].append(
                        {
                            "review_id": review.get("review_id"),
                            "text": text[:max_len] + ("…" if len(text) > max_len else ""),
                            "rating": review.get("rating"),
                            "review_date": review.get("review_date"),
                        }
                    )
        examples[aspect] = buckets
    return examples


@app.route("/dashboard/<int:aid>")
def dashboard(aid):
    data = database.get_analysis(aid)
    if not data:
        abort(404)
    # Normalize provenance on every read so legacy analyses gain stable review
    # IDs where exact evidence can be reconstructed. Presentation fields are
    # deterministic and intentionally recomputed from the persisted analysis.
    audience_insights.enrich_result(data)
    data["insights"] = insights.generate_insights(
        data.get("aspect_summary") or {}, data.get("keywords") or {},
        narrative=data.get("analysis_narrative") or {},
    )
    return render_template(
        "dashboard.html", a=data, aspect_examples=_aspect_examples(data)
    )


@app.route("/history")
def history():
    items = database.list_analyses()
    return render_template(
        "history.html", items=items, page="history",
        title="ประวัติการวิเคราะห์",
        subtitle="รายการวิเคราะห์ทั้งหมดของคุณ ({} รายการ)".format(len(items)),
        empty="ยังไม่มีประวัติการวิเคราะห์",
        empty_sub="เมื่อคุณวิเคราะห์ร้านอาหาร ผลลัพธ์จะถูกบันทึกไว้ที่นี่",
    )


@app.route("/saved")
def saved():
    items = database.list_saved()
    return render_template(
        "history.html", items=items, page="saved",
        title="รายการโปรด",
        subtitle="ร้านที่คุณบันทึกไว้ ({} รายการ)".format(len(items)),
        empty="ยังไม่มีรายการที่บันทึกไว้",
        empty_sub="กดไอคอนบุ๊กมาร์กบนผลวิเคราะห์เพื่อเก็บไว้ดูภายหลัง",
    )


@app.route("/toggle-save/<int:aid>", methods=["POST"])
def toggle_save(aid):
    is_saved = database.toggle_saved(aid)
    if is_saved is None:
        abort(404)
    return jsonify({"id": aid, "is_saved": is_saved})


@app.route("/delete/<int:aid>", methods=["POST"])
def delete(aid):
    ok = database.delete_analysis(aid)
    if not ok:
        abort(404)
    return jsonify({"id": aid, "deleted": ok})


@app.route("/delete-all", methods=["POST"])
def delete_all():
    deleted_count = database.delete_all_analyses()
    return jsonify({"deleted": True, "deleted_count": deleted_count})


@app.route("/api/analysis/<int:aid>")
def api_analysis(aid):
    data = database.get_analysis(aid)
    if not data:
        abort(404)
    return jsonify(data)


@app.route("/healthz")
def healthz():
    """Small dependency-free liveness/readiness probe for deployment."""
    try:
        database.healthcheck()
    except Exception as e:  # noqa: BLE001 - health endpoint must report, not raise
        log.error("database healthcheck failed: %s", e)
        return jsonify({"status": "unhealthy", "database": "unavailable"}), 503
    return jsonify({
        "status": "ok",
        "database": "ok",
        "jobs": job_runner.snapshot(),
    })


# ---------- legacy settings compatibility (UI ย้ายไปอยู่ข้างช่อง URLแล้ว) ----------
@app.route("/settings")
def settings():
    flash("ย้ายตัวเลือกการวิเคราะห์มาไว้ข้างช่องวางลิงก์แล้ว", "info")
    return redirect(url_for("index"))


@app.route("/settings", methods=["POST"])
def save_settings():
    changes = {"use_model": request.form.get("engine") == "model"}

    engine = request.form.get("extract_engine")
    if engine in ("rule", "llm"):
        changes["extract_engine"] = engine

    # จำนวนรีวิว: รับค่าแล้วให้ config บีบเข้าเพดาน [MIN_REVIEWS, MAX_REVIEWS_CAP] เอง
    try:
        changes["max_reviews"] = int(request.form.get("max_reviews", ""))
    except (TypeError, ValueError):
        pass

    config.save_settings(changes)
    flash("บันทึกค่าเริ่มต้นแล้ว ตัวเลือกอยู่ข้างช่องวางลิงก์", "ok")
    return redirect(url_for("index"))


# ---------- export (สำหรับงานวิจัย) ----------
def _download(text: str, filename: str, mime: str) -> Response:
    return Response(text, mimetype=mime, headers={
        "Content-Disposition": f"attachment; filename={filename}"
    })


@app.route("/export/<int:aid>/reviews.csv")
def export_reviews(aid):
    a = database.get_analysis(aid)
    if not a:
        abort(404)
    return _download(export.reviews_csv(a), f"reviews_{aid}.csv", "text/csv; charset=utf-8")


@app.route("/export/<int:aid>/summary.csv")
def export_summary(aid):
    a = database.get_analysis(aid)
    if not a:
        abort(404)
    return _download(export.summary_csv(a), f"summary_{aid}.csv", "text/csv; charset=utf-8")


@app.route("/export/<int:aid>/labeling.json")
def export_labeling(aid):
    a = database.get_analysis(aid)
    if not a:
        abort(404)
    return _download(export.labeling_json(a), f"for_labeling_{aid}.json",
                     "application/json; charset=utf-8")


# ---------- error pages (ไม่ให้เจอหน้า debug ดิบ) ----------
@app.errorhandler(400)
def bad_request(e):
    return render_template("error.html",
                           code="400", title="คำขอไม่ถูกต้อง",
                           message="คำขอหมดอายุหรือไม่ผ่านการตรวจสอบความปลอดภัย กรุณารีเฟรชหน้าแล้วลองใหม่"), 400


@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "not_found", "status": 404}), 404
    return render_template("error.html",
                           code="404", title="ไม่พบหน้านี้",
                           message="หน้าที่คุณเปิดอาจถูกลบไปแล้ว หรือไม่เคยมีอยู่"), 404


@app.errorhandler(413)
def request_too_large(e):
    return render_template("error.html",
                           code="413", title="คำขอมีขนาดใหญ่เกินไป",
                           message="ข้อมูลที่ส่งมาเกินขนาดที่ระบบรองรับ กรุณารีเฟรชหน้าแล้วลองใหม่"), 413


@app.errorhandler(500)
def server_error(e):
    return render_template("error.html",
                           code="500", title="ระบบขัดข้อง",
                           message="เกิดข้อผิดพลาดภายในระบบ ลองรีเฟรชหรือกลับหน้าแรก"), 500


if __name__ == "__main__":
    app.run(host=config.HOST, debug=config.DEBUG, port=config.PORT)
