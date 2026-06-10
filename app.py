"""
app.py
======
Flask application — จุดเข้าของเว็บทั้งหมด

Routes:
  GET  /                 หน้าแรก (ช่องวาง URL + ปุ่ม Analyze)
  POST /analyze          รับ URL -> รัน pipeline -> เก็บ DB -> redirect ไป dashboard
  GET  /dashboard/<id>   หน้าแสดงผลวิเคราะห์
  GET  /history          ประวัติการวิเคราะห์
  GET  /saved            รายการโปรด
  POST /toggle-save/<id> สลับสถานะรายการโปรด
  POST /delete/<id>      ลบผลวิเคราะห์
  GET  /api/analysis/<id> คืนผลเป็น JSON

หมายเหตุ: ทุก route ที่อาจล้มเหลว (โดยเฉพาะ /analyze ที่เรียก Apify/โมเดล)
ถูกครอบด้วย error handling เพื่อไม่ให้ผู้ใช้เจอหน้า 500 ดิบ ๆ
"""
import logging
from flask import (
    Flask, render_template, request, redirect, url_for, jsonify, abort, flash,
    Response,
)

import config
from core import pipeline, export
from db import database

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
database.init_db()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("insightreview")


@app.context_processor
def inject_globals():
    return {"demo_mode": not config.get_apify_token()}


def _looks_like_maps_url(url: str) -> bool:
    """ตรวจคร่าว ๆ ว่าเป็นลิงก์ Google Maps จริงไหม (กันยิง Apify ทิ้งเปล่า)"""
    u = url.lower()
    return any(s in u for s in (
        "google.com/maps", "google.co.th/maps", "maps.google",
        "goo.gl/maps", "maps.app.goo.gl", "/maps/place", "?cid=",
    ))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    url = (request.form.get("url") or "").strip()

    # โหมดจริง (มี Apify token): ต้องมี URL และต้องเป็นลิงก์ Maps
    if config.get_apify_token():
        if not url:
            flash("กรุณาวางลิงก์ร้านจาก Google Maps ก่อนเริ่มวิเคราะห์", "err")
            return redirect(url_for("index"))
        if not _looks_like_maps_url(url):
            flash("ลิงก์ไม่ถูกต้อง — ใช้ลิงก์ร้านอาหารจาก Google Maps เท่านั้น", "err")
            return redirect(url_for("index"))

    # รัน pipeline แบบกัน error: ถ้าพัง ผู้ใช้ต้องเห็นข้อความที่เข้าใจได้ ไม่ใช่ 500 ดิบ
    try:
        result = pipeline.run_analysis(url)
    except Exception as e:  # noqa: BLE001 (จับกว้างเพื่อกัน user เจอ traceback)
        log.exception("analyze failed: %s", e)
        flash("วิเคราะห์ไม่สำเร็จ — อาจดึงรีวิวไม่ได้หรือบริการขัดข้อง ลองใหม่อีกครั้ง", "err")
        return redirect(url_for("index"))

    # ไม่มีรีวิวภาษาไทยให้วิเคราะห์เลย
    if result.get("total_reviews", 0) == 0:
        flash("ไม่พบรีวิวภาษาไทยที่ร้านนี้ ลองร้านอื่นหรือเพิ่มจำนวนรีวิว", "err")
        return redirect(url_for("index"))

    aid = database.save_analysis(result)
    return redirect(url_for("dashboard", aid=aid))


@app.route("/dashboard/<int:aid>")
def dashboard(aid):
    data = database.get_analysis(aid)
    if not data:
        abort(404)
    return render_template("dashboard.html", a=data)


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
    return jsonify({"id": aid, "is_saved": is_saved})


@app.route("/delete/<int:aid>", methods=["POST"])
def delete(aid):
    ok = database.delete_analysis(aid)
    return jsonify({"id": aid, "deleted": ok})


@app.route("/api/analysis/<int:aid>")
def api_analysis(aid):
    data = database.get_analysis(aid)
    if not data:
        abort(404)
    return jsonify(data)


# ---------- settings (ผู้ใช้ทั่วไปปรับได้: โมเดล + จำนวนรีวิว) ----------
@app.route("/settings")
def settings():
    return render_template(
        "settings.html",
        s=config.get_settings(),
        max_cap=config.MAX_REVIEWS_CAP,
        min_reviews=config.MIN_REVIEWS,
    )


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
    flash("บันทึกการตั้งค่าแล้ว", "ok")
    return redirect(url_for("settings"))


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
@app.errorhandler(404)
def not_found(e):
    return render_template("error.html",
                           code="404", title="ไม่พบหน้านี้",
                           message="หน้าที่คุณเปิดอาจถูกลบไปแล้ว หรือไม่เคยมีอยู่"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("error.html",
                           code="500", title="ระบบขัดข้อง",
                           message="เกิดข้อผิดพลาดภายในระบบ ลองรีเฟรชหรือกลับหน้าแรก"), 500


if __name__ == "__main__":
    app.run(debug=config.DEBUG, port=config.PORT)
