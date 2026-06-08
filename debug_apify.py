"""
debug_apify.py — รันตัวนี้เพื่อหาว่าปัญหาอยู่ตรงไหน

วิธีรัน (จาก root โปรเจกต์):
    python debug_apify.py
"""
import os, sys, json, requests

TOKEN = os.environ.get("APIFY_TOKEN","").strip()

# ---- ขั้น 1: มี token ไหม? ----
print("=" * 50)
print("ขั้น 1 — ตรวจ APIFY_TOKEN")
if not TOKEN:
    print("  ❌  ไม่เจอ APIFY_TOKEN ในระบบ!")
    print()
    print("  แก้: ตั้งค่าใน terminal เดียวกันกับที่รัน debug นี้")
    print("  Windows CMD :  set APIFY_TOKEN=apify_api_xxxx")
    print("  Mac / Linux :  export APIFY_TOKEN=apify_api_xxxx")
    sys.exit(1)
else:
    masked = TOKEN[:12] + "..." + TOKEN[-4:]
    print(f"  ✅  พบ token: {masked}  (ยาว {len(TOKEN)} ตัวอักษร)")

# ---- ขั้น 2: token ใช้งานได้ไหม? ----
print()
print("ขั้น 2 — ทดสอบ token กับ Apify API")
try:
    r = requests.get(
        "https://api.apify.com/v2/users/me",
        params={"token": TOKEN}, timeout=15
    )
    if r.status_code == 200:
        me = r.json().get("data", {})
        print(f"  ✅  login สำเร็จ: {me.get('username','?')} "
              f"| plan: {me.get('plan',{}).get('id','?')}")
        credits = me.get("monthlyUsage", {}).get("computeUnits", "?")
        print(f"      compute units ที่ใช้เดือนนี้: {credits}")
    else:
        print(f"  ❌  token ไม่ถูกต้อง (HTTP {r.status_code})")
        print(f"      {r.text[:200]}")
        sys.exit(1)
except Exception as e:
    print(f"  ❌  เชื่อมต่อ Apify ไม่ได้: {e}")
    sys.exit(1)

# ---- ขั้น 3: ทดสอบ scrape URL ตัวอย่าง ----
print()
print("ขั้น 3 — ทดสอบดึงรีวิวจาก Google Maps")
TEST_URL = "https://maps.app.goo.gl/Juif524nahAVtqTt7"
print(f"  URL: {TEST_URL}")
print("  รอสักครู่...")

ENDPOINT = (
    "https://api.apify.com/v2/acts/"
    "compass~google-maps-reviews-scraper/run-sync-get-dataset-items"
)
try:
    resp = requests.post(
        ENDPOINT,
        params={"token": TOKEN},
        json={
            "startUrls": [{"url": TEST_URL}],
            "maxReviews": 5,          # ขอแค่ 5 ก่อน เพื่อทดสอบเร็วๆ
            "reviewsSort": "newest",
        },
        timeout=180,                   # รอ 3 นาที
    )
    print(f"  HTTP status: {resp.status_code}")

    if resp.status_code == 200:
        items = resp.json()
        print(f"  ✅  ได้ {len(items)} รายการ")
        if items:
            first = items[0]
            print(f"  ฟิลด์ที่ได้: {list(first.keys())}")
            print(f"  ข้อความรีวิว: {str(first.get('text','(ไม่มีฟิลด์ text)'))[:80]}")
            print(f"  คะแนน:        {first.get('stars', first.get('rating','?'))}")
            print(f"  ชื่อร้าน:     {first.get('title', first.get('placeName','?'))}")
        else:
            print("  ⚠️  ได้ 0 รีวิว — ดูเหตุผลที่เป็นไปได้ด้านล่าง")
    elif resp.status_code == 400:
        print(f"  ❌  input ผิด: {resp.text[:300]}")
    elif resp.status_code == 408:
        print("  ⏱️  timeout — actor ใช้เวลานานเกินไป ลองเพิ่ม timeout หรือใช้โหมด async")
    else:
        print(f"  ❌  error: {resp.text[:300]}")

except requests.Timeout:
    print("  ⏱️  timeout (3 นาที) — Apify ยังไม่ตอบ")
    print("  แก้: เพิ่ม APIFY_TIMEOUT ใน config หรือเปลี่ยนเป็น async mode")
except Exception as e:
    print(f"  ❌  error: {e}")

print()
print("=" * 50)
print("รายงานเสร็จแล้ว")
