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
import tempfile
import threading

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


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    """Read a bounded integer environment variable without breaking startup."""
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError, OverflowError):
        value = default
    return max(minimum, min(maximum, value))

# ---- Apify (การดึงรีวิว) ----
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "").strip()
APIFY_TIMEOUT = _env_int("APIFY_TIMEOUT", 300, 1, 900)   # วินาที
MAX_REVIEWS = _env_int("MAX_REVIEWS", 100, 10, 1000)     # ดึงต่อร้านกี่รีวิว


# ---- โมเดลวิเคราะห์อารมณ์ ----
# USE_MODEL=1 เพื่อใช้ WangchanBERTa จริง (ต้องลง transformers+torch และมีเน็ตโหลดโมเดล)
USE_MODEL = os.environ.get("USE_MODEL", "0") == "1"
MODEL_NAME = os.environ.get(
    "MODEL_NAME", "airesearch/wangchanberta-base-att-spm-uncased"
)
# revision ที่ fine-tune มาแล้ว: wisesight_sentiment (4 คลาส) — เราแมป question -> neutral
MODEL_REVISION = os.environ.get("MODEL_REVISION", "finetuned@wisesight_sentiment")

# ---- Google Gemini (เครื่องยนต์สกัดวลี LLM — ทางเลือก opt-in, ฟรีจาก AI Studio) ----
# โมเดลอ่านตอน import; API key อ่านสดผ่าน get_gemini_api_key() (เผื่อ patch ใน test)
# ใช้โมเดล stable ที่ Google เปิดให้ผู้ใช้ใหม่และมี free tier
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash").strip()

# ---- Flask ----
# DEBUG ปิดเป็นค่าเริ่มต้น (เปิดด้วย FLASK_DEBUG=1 ตอนพัฒนาเท่านั้น)
# เหตุผลความปลอดภัย: debug=True เปิด Werkzeug debugger ซึ่งรันโค้ดได้จากเบราว์เซอร์
# (เท่ากับ RCE ถ้าแอปเข้าถึงได้จากภายนอก) จึงห้ามเปิดในเครื่องที่คนอื่นเข้าถึงได้
DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"
HOST = os.environ.get("HOST", "127.0.0.1").strip() or "127.0.0.1"
PORT = _env_int("PORT", 5000, 1, 65535)
WEB_THREADS = _env_int("WEB_THREADS", 4, 1, 64)
SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0").strip().lower() in {
    "1", "true", "yes", "on",
}
ANALYZE_MAX_REQUESTS = _env_int("ANALYZE_MAX_REQUESTS", 10, 0, 10000)
ANALYZE_WINDOW_SECONDS = _env_int("ANALYZE_WINDOW_SECONDS", 3600, 10, 86400)
ANALYZE_MAX_CONCURRENT = _env_int("ANALYZE_MAX_CONCURRENT", 3, 1, 16)
ANALYZE_MAX_QUEUED = _env_int("ANALYZE_MAX_QUEUED", 10, 0, 1000)
WANGCHAN_MAX_CONCURRENT = _env_int("WANGCHAN_MAX_CONCURRENT", 2, 1, 4)
JOB_RETENTION_DAYS = _env_int("JOB_RETENTION_DAYS", 7, 1, 365)

# SECRET_KEY: ใช้ค่าจาก env ถ้ามี (เซสชันคงที่ข้ามการรีสตาร์ท)
# ถ้าไม่ตั้ง -> สุ่มคีย์แข็งแรงต่อโปรเซส แทนคีย์ตายตัวที่เดาได้
# (แอปนี้ไม่มีระบบล็อกอิน เซสชันใช้ flash message + CSRF token; production ควรตั้งค่าคงที่)
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
# ค่าเริ่มต้นของแบบฟอร์ม (เก็บใน data/settings.json เพื่อ compatibility):
# ผู้ใช้เลือก use_model / extract_engine / max_reviews ต่อหนึ่งงานข้างช่อง URL
# และค่าจากงานหนึ่งจะไม่เปลี่ยนค่าร่วมของงานอื่น
import json   # noqa: E402

SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")

MIN_REVIEWS = 10                 # ขั้นต่ำที่ยอมให้เลือก
MAX_REVIEWS_CAP = MAX_REVIEWS    # เพดานจาก .env (operator กำหนด)

# ค่าตั้งต้นของฝั่งผู้ใช้ (ใช้เมื่อยังไม่เคยตั้งค่าทับ)
_DEFAULTS = {
    "max_reviews": MAX_REVIEWS_CAP,   # เริ่มต้น = ใช้เต็มเพดาน
    "use_model": USE_MODEL,
    "extract_engine": "rule",     # "rule" (lexicon pipeline) | "llm" (Gemini)
}

# cache อ่านไฟล์ตาม mtime กันอ่านซ้ำทุกรีวิว
_settings_cache = {"path": None, "mtime": None, "data": {}}
_settings_lock = threading.RLock()


def _coerce_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _coerce_bool(value, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _load_overrides() -> dict:
    with _settings_lock:
        try:
            mtime = os.stat(SETTINGS_PATH).st_mtime_ns
        except OSError:
            return {}
        if (_settings_cache["path"], _settings_cache["mtime"]) == (SETTINGS_PATH, mtime):
            return dict(_settings_cache["data"] or {})

        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                loaded = json.load(f)
            _settings_cache["data"] = loaded if isinstance(loaded, dict) else {}
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            _settings_cache["data"] = {}
        _settings_cache["path"] = SETTINGS_PATH
        _settings_cache["mtime"] = mtime
        return dict(_settings_cache["data"])


def get_settings() -> dict:
    """ค่าฝั่งผู้ใช้ที่ใช้จริง (override ทับ default + บีบ max_reviews ให้อยู่ในเพดาน)"""
    with _settings_lock:
        o = _load_overrides()
        raw_max = _coerce_int(o.get("max_reviews"), _DEFAULTS["max_reviews"])
        return {
            "max_reviews": max(MIN_REVIEWS, min(MAX_REVIEWS_CAP, raw_max)),
            "use_model": _coerce_bool(
                o.get("use_model"), _DEFAULTS["use_model"]
            ),
            "extract_engine": (
                o.get("extract_engine")
                if o.get("extract_engine") in ("rule", "llm")
                else _DEFAULTS["extract_engine"]
            ),
        }


def save_settings(changes: dict) -> None:
    """บันทึกเฉพาะ key ที่ผู้ใช้ปรับได้ (กันเขียน key อื่นปนเข้ามา)"""
    with _settings_lock:
        current = get_settings()
        normalized = {}
        if "max_reviews" in changes:
            raw_max = _coerce_int(changes["max_reviews"], current["max_reviews"])
            normalized["max_reviews"] = max(
                MIN_REVIEWS, min(MAX_REVIEWS_CAP, raw_max)
            )
        if "use_model" in changes:
            normalized["use_model"] = _coerce_bool(
                changes["use_model"], current["use_model"]
            )
        if changes.get("extract_engine") in ("rule", "llm"):
            normalized["extract_engine"] = changes["extract_engine"]

        overrides = dict(_load_overrides())
        overrides.update(normalized)
        settings_dir = os.path.dirname(os.path.abspath(SETTINGS_PATH))
        os.makedirs(settings_dir, exist_ok=True)

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=settings_dir,
                prefix=".settings-",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                temp_path = temp_file.name
                json.dump(overrides, temp_file, ensure_ascii=False, indent=2)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            os.replace(temp_path, SETTINGS_PATH)
            temp_path = None
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

        _settings_cache.update({"path": None, "mtime": None, "data": {}})


def get_apify_token() -> str:
    """token มาจาก .env เท่านั้น (operator) — ไม่เปิดให้ user แก้ผ่าน UI"""
    return APIFY_TOKEN


def get_max_reviews() -> int:
    return get_settings()["max_reviews"]


def get_use_model() -> bool:
    return get_settings()["use_model"]


def get_extract_engine() -> str:
    return get_settings()["extract_engine"]


def get_gemini_api_key() -> str:
    """API key ของ Gemini (อ่านสดจาก env) — ว่าง = เครื่องยนต์ LLM ปิด/ไม่พร้อมใช้"""
    return os.environ.get("GEMINI_API_KEY", "").strip()
