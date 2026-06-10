"""
config.py
=========
ตั้งค่ากลางของระบบทั้งหมด อ่านค่าจาก environment variable ได้
เพื่อให้สลับ "โหมด demo" กับ "โหมดจริง" โดยไม่ต้องแก้โค้ด

วิธีเปิดโหมดจริง (ตอนพร้อม):
  ตั้ง env:  APIFY_TOKEN=<token ของคุณ>   -> ดึงรีวิวจริงจาก Google Maps
  ตั้ง env:  USE_MODEL=1                   -> ใช้ WangchanBERTa จริง
  (ถ้าไม่ตั้ง -> รันโหมด demo ได้ทันที ใช้ข้อมูลตัวอย่าง + lexicon)
"""
import os
import secrets

# ---- พาธ ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")


# ---- โหลดไฟล์ .env อัตโนมัติ (ถ้ามี) ----
# ใส่ค่าในไฟล์ .env ครั้งเดียว ไม่ต้อง set ใหม่ทุกครั้งที่เปิด terminal
def _load_dotenv():
    path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            val = val.strip().strip('"').strip("'")
            os.environ.setdefault(key.strip(), val)   # env จริงมาก่อน .env เสมอ


_load_dotenv()

# ---- Apify (การดึงรีวิว) ----
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "").strip()
APIFY_TIMEOUT = int(os.environ.get("APIFY_TIMEOUT", "300"))   # วินาที
MAX_REVIEWS = int(os.environ.get("MAX_REVIEWS", "300"))       # ดึงต่อร้านกี่รีวิว


# ---- โมเดลวิเคราะห์อารมณ์ ----
# USE_MODEL=1 เพื่อใช้ WangchanBERTa จริง (ต้องลง transformers+torch และมีเน็ตโหลดโมเดล)
USE_MODEL = os.environ.get("USE_MODEL", "0") == "1"
MODEL_NAME = os.environ.get(
    "MODEL_NAME", "airesearch/wangchanberta-base-att-spm-uncased"
)
# revision ที่ fine-tune มาแล้ว: wisesight_sentiment (4 คลาส) — เราแมป question -> neutral
MODEL_REVISION = os.environ.get("MODEL_REVISION", "finetuned@wisesight_sentiment")

# ---- Flask ----
# DEBUG ปิดเป็นค่าเริ่มต้น (เปิดด้วย FLASK_DEBUG=1 ตอนพัฒนาเท่านั้น)
# เหตุผลความปลอดภัย: debug=True เปิด Werkzeug debugger ซึ่งรันโค้ดได้จากเบราว์เซอร์
# (เท่ากับ RCE ถ้าแอปเข้าถึงได้จากภายนอก) จึงห้ามเปิดในเครื่องที่คนอื่นเข้าถึงได้
DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"
PORT = int(os.environ.get("PORT", "5000"))

# SECRET_KEY: ใช้ค่าจาก env ถ้ามี (เซสชันคงที่ข้ามการรีสตาร์ท)
# ถ้าไม่ตั้ง -> สุ่มคีย์แข็งแรงต่อโปรเซส แทนคีย์ตายตัวที่เดาได้
# (แอปนี้ไม่มีระบบล็อกอิน เซสชันใช้แค่ flash message การสุ่มต่อโปรเซสจึงไม่กระทบผู้ใช้)
def resolve_secret_key(env_value: str):
    """Return (key, used_random). A blank env value yields a strong per-process
    random key (good enough for this app's flash-only sessions) but the caller
    should warn: under multiple workers each process gets a different key, so set
    SECRET_KEY in production for stable sessions."""
    env_value = (env_value or "").strip()
    if env_value:
        return env_value, False
    return secrets.token_hex(32), True


SECRET_KEY, _SECRET_KEY_IS_RANDOM = resolve_secret_key(os.environ.get("SECRET_KEY", ""))
if _SECRET_KEY_IS_RANDOM:
    try:
        print("[config] ⚠️  SECRET_KEY not set — using a random per-process key. "
              "Set SECRET_KEY in production (multi-worker sessions break otherwise).")
    except UnicodeEncodeError:
        print("[config] WARNING: SECRET_KEY not set - using a random per-process key. "
              "Set SECRET_KEY in production (multi-worker sessions break otherwise).")


# ---------------------------------------------------------------------------
# การตั้งค่า: แยกชัดระหว่าง "ผู้ดูแลระบบ" กับ "ผู้ใช้ทั่วไป"
# ---------------------------------------------------------------------------
# ผู้ดูแลระบบ (ตั้งใน .env เท่านั้น — ผู้ใช้ทั่วไปแก้ไม่ได้ผ่าน UI):
#   - APIFY_TOKEN  : กุญแจดึงรีวิว (operator เป็นคนจ่ายค่า Apify จึงไม่เปิดให้ user ใส่เอง)
#   - MAX_REVIEWS  : "เพดาน" จำนวนรีวิวต่อครั้ง — user เลือกได้ไม่เกินค่านี้ (กันเปลืองเครดิต)
#
# ผู้ใช้ทั่วไป (ปรับได้จากหน้า Settings -> เก็บลง data/settings.json, มีผลทันทีไม่ต้อง restart):
#   - use_model    : เลือกเครื่องมือวิเคราะห์ (WangchanBERTa / lexicon)
#   - max_reviews  : จำนวนรีวิวที่อยากวิเคราะห์ (ถูกบีบให้อยู่ในช่วง [10, MAX_REVIEWS])
import json   # noqa: E402

SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")

MIN_REVIEWS = 10                 # ขั้นต่ำที่ยอมให้เลือก
MAX_REVIEWS_CAP = MAX_REVIEWS    # เพดานจาก .env (operator กำหนด)

# ค่าตั้งต้นของฝั่งผู้ใช้ (ใช้เมื่อยังไม่เคยตั้งค่าทับ)
_DEFAULTS = {
    "max_reviews": MAX_REVIEWS_CAP,   # เริ่มต้น = ใช้เต็มเพดาน
    "use_model": USE_MODEL,
    "extract_engine": "rule",     # "rule" (lexicon pipeline) | "llm" (Claude)
}

# cache อ่านไฟล์ตาม mtime กันอ่านซ้ำทุกรีวิว
_settings_cache = {"mtime": None, "data": {}}


def _load_overrides() -> dict:
    try:
        mtime = os.path.getmtime(SETTINGS_PATH)
    except OSError:
        return {}
    if _settings_cache["mtime"] != mtime:
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                _settings_cache["data"] = json.load(f)
            _settings_cache["mtime"] = mtime
        except Exception:
            _settings_cache["data"] = {}
    return _settings_cache["data"] or {}


def get_settings() -> dict:
    """ค่าฝั่งผู้ใช้ที่ใช้จริง (override ทับ default + บีบ max_reviews ให้อยู่ในเพดาน)"""
    o = _load_overrides()
    raw_max = int(o.get("max_reviews", _DEFAULTS["max_reviews"]))
    return {
        "max_reviews": max(MIN_REVIEWS, min(MAX_REVIEWS_CAP, raw_max)),
        "use_model": bool(o.get("use_model", _DEFAULTS["use_model"])),
        "extract_engine": (o.get("extract_engine") if o.get("extract_engine") in ("rule", "llm")
                           else _DEFAULTS["extract_engine"]),
    }


def save_settings(changes: dict) -> None:
    """บันทึกเฉพาะ key ที่ผู้ใช้ปรับได้ (กันเขียน key อื่นปนเข้ามา)"""
    allowed = {"max_reviews", "use_model", "extract_engine"}
    o = dict(_load_overrides())
    o.update({k: v for k, v in changes.items() if k in allowed})
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(o, f, ensure_ascii=False, indent=2)
    _settings_cache["mtime"] = None   # บังคับ reload ครั้งหน้า


def get_apify_token() -> str:
    """token มาจาก .env เท่านั้น (operator) — ไม่เปิดให้ user แก้ผ่าน UI"""
    return APIFY_TOKEN


def get_max_reviews() -> int:
    return get_settings()["max_reviews"]


def get_use_model() -> bool:
    return get_settings()["use_model"]


def get_extract_engine() -> str:
    return get_settings()["extract_engine"]
