# InsightReview

เว็บแอปวิเคราะห์รีวิวร้านอาหารจาก Google Maps:
ดึงรีวิว → คัดเฉพาะภาษาไทย + ทำความสะอาด → จำแนกอารมณ์ (บวก/กลาง/ลบ) →
**สกัด "วลีความเห็น" (opinion phrases)** แยกตามหมวด (อาหาร/บริการ/บรรยากาศ) →
สรุปข้อเสนอแนะเชิงปฏิบัติ → แสดงผลแยกมุมมองผู้บริโภคและผู้ประกอบการ

> โครงงาน วท.บ. เทคโนโลยีสารสนเทศ มหาวิทยาลัยนเรศวร

จุดเด่นของระบบคือ **ไม่ได้ดึง "คำเดี่ยว"** (เช่น `อาหาร`, `ดี`, `อร่อย`) แต่ดึง
**วลีที่นำไปใช้ตัดสินใจได้จริง** เช่น `อาหารอร่อย`, `ราคาไม่แพง`, `รอนาน`,
`ติดริมน้ำ`, `บริการรวดเร็ว` พร้อมจำแนกหมวดและอารมณ์ของแต่ละวลี

---

## ✨ รันได้ทันทีด้วย "โหมด demo"

ออกแบบให้ **รันได้เลยโดยไม่ต้องมี Apify token และไม่ต้องโหลดโมเดล** — เหมาะกับการ
พัฒนา/ทดสอบ flow ทั้งระบบ

```bash
# 1) ติดตั้ง dependency (เบา)
pip install -r requirements.txt

# 2) รัน
python app.py

# 3) เปิดเบราว์เซอร์ http://127.0.0.1:5000
#    วาง URL อะไรก็ได้ (โหมด demo จะใช้ข้อมูลตัวอย่างแทน) แล้วกด Analyze
```

โหมด demo จะ:
- ใช้รีวิวตัวอย่าง **30 รายการ** ใน `data/sample_reviews.json` (ร้าน "ครัวบ้านสวน") แทน Apify
- จำแนกอารมณ์ด้วย **lexicon** (พจนานุกรมคำบวก/ลบ + คำปฏิเสธ) แทน WangchanBERTa
- ทำงานครบทุกขั้นตอนที่เหลือเหมือนจริง (สกัดวลี, จัดหมวด, สรุป, แดชบอร์ด, history, save, export)

แดชบอร์ดมี badge บอกว่ากำลังใช้เครื่องมือใด — `lexicon (พจนานุกรมคำ)` หรือ `WangchanBERTa`
(รายงานตามสถานะจริง ถ้าโมเดลโหลดไม่สำเร็จจะ fallback มา lexicon และแจ้งให้ทราบ)

---

## 🏭 รันแบบ production

เมื่อติดตั้ง `requirements.txt` แล้ว ให้ใช้ Waitress แทน Flask development server:

```bash
# ตั้ง SECRET_KEY แบบยาวและคงที่ใน .env ก่อน
python serve.py
```

ค่าเริ่มต้นฟังที่ `127.0.0.1:5000`; ปรับ `HOST`, `PORT` และ `WEB_THREADS` ใน `.env`
ได้ตามระบบ deploy และใช้ `GET /healthz` เป็น readiness probe ซึ่งตรวจทั้ง SQLite และ
รายงานสถานะความจุของคิว (`capacity`, `inflight`, `available`) ตัวประมวลผลเบื้องหลังเป็น
in-process queue จึงควรรันเว็บเพียง **1 process**; เพิ่ม HTTP threads ได้ แต่ไม่ควรเปิดหลาย
process จนกว่าจะย้ายคิว/rate limit ไป Redis/Celery/RQ

---

## 🚀 เปิด "โหมดจริง"

ตั้งค่าผ่านไฟล์ `.env` (คัดลอกจาก `.env.example`) — เปิดแยกกันได้อิสระ จะเปิดแค่ Apify,
แค่โมเดล หรือทั้งคู่ก็ได้

```bash
cp .env.example .env     # Windows: copy .env.example .env
```

### (ก) ดึงรีวิวจริงจาก Google Maps ด้วย Apify
1. สมัคร [Apify](https://apify.com) (มีเครดิตฟรี) แล้วคัดลอก API token
2. ใส่ใน `.env`:
   ```
   APIFY_TOKEN=apify_api_xxxxxxxxxxxxx
   MAX_REVIEWS=100
   ```
ใช้ actor `compass/google-maps-reviews-scraper` (ดู `core/scraper.py`).
มีสคริปต์ตรวจการเชื่อมต่อ: `python debug_apify.py`

### (ข) ใช้ WangchanBERTa วิเคราะห์อารมณ์จริง
1. ติดตั้งโมเดล (หนักหน่อย — torch ~2GB, โมเดลโหลดครั้งแรกอัตโนมัติ):
   ```bash
   pip install -r requirements-model.txt
   ```
2. ตั้งใน `.env`: `USE_MODEL=1`

โมเดล: `airesearch/wangchanberta-base-att-spm-uncased`
revision `finetuned@wisesight_sentiment` (4 คลาส — โค้ดแมป "question" → neutral)
รันบน CPU ได้แต่ช้า; ถ้าจะ **fine-tune** แนะนำทำบน Google Colab

> ผู้ใช้เลือกเครื่องมือวิเคราะห์วลี เครื่องมือวิเคราะห์อารมณ์ และจำนวนรีวิวได้
> **ข้างช่องวาง URL ก่อนกด Analyze** โดยตัวเลือกมีผลเฉพาะงานนั้นและไม่แก้ค่าร่วมของระบบ
> ส่วน `APIFY_TOKEN` และเพดานจำนวนรีวิว (`MAX_REVIEWS`) ยังเป็นค่าฝั่งเซิร์ฟเวอร์ใน `.env`

ดูค่าทั้งหมดได้ที่ `.env.example`

---

## 🔬 วิธีการสกัดวลีความเห็น (Methodology — Review Insight)

หัวใจของระบบคือ pipeline ที่ทุกขั้นตอนเป็น **deterministic และอธิบายได้** (ไม่ใช่กล่องดำ)
ทำงานทีละ "อนุประโยค" (clause):

```
รีวิว
 └─ คัดไทย + ทำความสะอาด + ตัดคำ          core/preprocess.py
     └─ แบ่งอนุประโยคตามคำเชื่อมขัดแย้ง       core/clause.py   (แต่ / แต่ว่า / อย่างไรก็ตาม)
         1. สกัดวลี (extract)              core/phrases/extract.py
         2. กรองคุณภาพ (quality)           core/phrases/quality.py
         3. ทำรูปมาตรฐาน (canonical)        core/phrases/canonical.py
         4. รวมคำพ้อง (synonyms)           core/phrases/synonyms.py
         5. จัดหมวด 4 ชั้น (aspect)         core/aspect.py
         6. จำแนกอารมณ์ตามบริบท (sentiment) core/sentiment.py
         7. นับ + จัดอันดับ (aggregate)     core/phrases/aggregate.py
 → แดชบอร์ด (วลี × หมวด × อารมณ์) + ข้อสรุปเชิงปฏิบัติ
```

แนวคิดสำคัญ:

- **ระดับอนุประโยค (clause-level):** `"อาหารอร่อย แต่บริการช้า"` ถูกแยกเป็น 2 อนุประโยค
  เพื่อผูกอารมณ์เข้าหมวดให้ตรง — "บริการ" จะไม่ถูกนับว่าบวกจากการชมอาหาร
- **คำปฏิเสธ (negation):** รวม "ไม่ + คำขั้ว" เป็นวลีเดียว (`ไม่อร่อย`, `ราคาไม่แพง`,
  `ไม่ประทับใจ`) กันความหมายกลับด้าน
- **สกัดเชิงพจนานุกรม ไม่พึ่ง POS:** เราประเมินตัวระบุชนิดคำ (POS tagging) ของ PyThaiNLP
  แล้วพบว่า**ติดป้ายคำแสดงความเห็นไทยผิดบ่อย** ในทุก corpus ที่ลอง (เช่น `อร่อย`→NOUN,
  `ดี`→ADV, `จัดจ้าน`→NOUN) จึงเลือกใช้ **ไวยากรณ์เชิงพจนานุกรมที่กำหนดเอง**
  (idiom/วลีตายตัว + คู่ "คำนามหัวหมวด + คำขยาย" + การกู้คำประสมจาก lexicon เช่น `รอ`+`นาน`→`รอนาน`)
  ซึ่งคงเส้นคงวาและอธิบายได้ แทนการพึ่ง POS ที่ไม่น่าเชื่อถือ
- **รวมคำพ้องแบบอนุรักษ์นิยม:** รวมเฉพาะวลีที่สื่อความ "เดียวกันจริง"
  (`ราคาไม่แพง` / `ราคาดี` / `คุ้มค่า` → `ราคาคุ้มค่า`) แต่ **ไม่รวม** คำบรรยายที่ต่างความหมาย
  (`อร่อย` ≠ `จัดจ้าน` ≠ `เข้มข้น`)
- **จัดหมวด 4 ชั้น (เรียงจากแม่นไปหลวม):** idiom/คอนเซ็ปต์ → คำนามหัวหมวด → บริบทอนุประโยค
  → คำขยายบ่งหมวด — รองรับวลีไร้คำนาม เช่น `ติดริมน้ำ`, `เย็นสบาย`, `คึกคัก`
- **แยก "การสกัด" ออกจาก "การตัดสินอารมณ์":** อารมณ์ของแต่ละวลีใช้ **"ขั้วของวลีเอง" เป็นหลัก**
  (เช่น `ราคาแพง` = ลบ, `ราคาไม่แพง` = บวก แม้อยู่ในประโยคบวก) ใช้ **บริบทอนุประโยค**
  เฉพาะวลีที่ไม่มีขั้วในตัว เช่น `คนเยอะ`

### เกณฑ์ "วลีที่ดี" กับ "วลีที่ตัดทิ้ง"

| ✅ เก็บ (นำไปใช้ได้) | ❌ ตัดทิ้ง (ข้อมูลน้อย) |
|---|---|
| `อาหารอร่อย`, `รสชาติจัดจ้าน`, `ราคาไม่แพง` | คำนามหัวหมวดเดี่ยว: `อาหาร`, `เมนู`, `ร้าน` |
| `บริการรวดเร็ว`, `รอนาน`, `พนักงานหยาบคาย` | คำบรรยายเดี่ยวกว้าง ๆ: `ดี`, `อร่อย` (จะถูกเติมหัว → `อาหารอร่อย` หรือถ้ากำกวมจะถูกทิ้ง) |
| `บรรยากาศดี`, `ติดริมน้ำ`, `เย็นสบาย`, `คึกคัก` | คำชวนเชียร์/อภิปราย: `ชอบ`, `แนะนำ` |

---

## 🤖 เครื่องยนต์สกัดวลี (Extraction engines)

ระบบเลือกได้ 2 เครื่องยนต์สำหรับ "การสกัดวลี" (เลือกข้างช่อง URL ก่อนวิเคราะห์):

- **Rule-based (ค่าเริ่มต้น):** pipeline เชิงพจนานุกรมตามหัวข้อด้านบน — ทำงาน
  **ออฟไลน์ ไม่มีค่าใช้จ่าย และอธิบายผลลัพธ์ได้ทุกขั้นตอน**
- **Gemini (LLM) — เลือกใช้เพิ่มเติม (opt-in):** ส่งรีวิวให้ Google Gemini สกัดวลี
  พร้อมสร้างบทสรุปภาษาไทย เรื่องที่ควรรู้ และคำแนะนำผู้ประกอบการใน request เดียว
  ทุกข้อสรุปต้องมีข้อความอ้างอิงตรงจากรีวิวจริง ระบบจะตัดข้อที่ตรวจหลักฐานไม่ได้
  และใช้ Rule-based เติมผลที่ยืนยันได้ เพื่อไม่ให้โหมด Gemini แย่กว่าระบบพื้นฐาน

### ตั้งค่า

ตั้งค่าใน `.env`:

- `GEMINI_API_KEY` — **ต้องตั้งค่านี้** เพื่อเปิดใช้เครื่องยนต์ Gemini
  (ขอ key ฟรีที่ [Google AI Studio](https://aistudio.google.com))
- `GEMINI_MODEL` (ไม่บังคับ) — ค่าเริ่มต้น `gemini-3.5-flash` ซึ่งเป็นรุ่น stable
  ที่รองรับ free tier และ structured output ที่ระบบใช้สกัดประเด็น

และต้องติดตั้ง SDK: `pip install google-genai` (อยู่ใน `requirements.txt` แล้ว)

ถ้าไม่ได้ตั้ง `GEMINI_API_KEY` (หรือไม่ได้ติดตั้ง `google-genai` SDK) หรือเรียก API
แล้วเกิดข้อผิดพลาด ระบบจะ **fallback กลับไปใช้ rule-based โดยอัตโนมัติ** —
เลือก "Gemini (LLM)" ก่อนวิเคราะห์ได้โดยไม่ทำให้ระบบล่ม

### ค่าใช้จ่าย

Gemini มี **free tier** จาก Google AI Studio (มีลิมิตจำนวนคำขอต่อนาที/ต่อวัน) —
การวิเคราะห์หนึ่งครั้งส่งรีวิวทั้งชุดเป็น request เดียว จึงอยู่ในโควตาฟรีได้สบายสำหรับ
งานระดับโครงงาน

---

## 🗂 แผนผังโค้ด

```
insightreview/
├── app.py                 # Flask: route ทั้งหมด (ดูหัวข้อ "หน้าเว็บ & API")
├── serve.py               # production entrypoint (Waitress, single process)
├── config.py              # ค่ากลางจาก .env + การตั้งค่าฝั่งผู้ใช้ (settings.json)
├── background_jobs.py     # bounded ThreadPoolExecutor สำหรับงานวิเคราะห์เบื้องหลัง
├── request_limits.py      # rate limit ต่อ IP + จำกัดงานวิเคราะห์พร้อมกัน
├── web_security.py        # CSRF + browser security headers
│
├── core/                  # ตรรกะการวิเคราะห์
│   ├── scraper.py         #  ดึงรีวิว: Apify จริง / sample เมื่อ demo
│   ├── preprocess.py      #  คัดไทย + ทำความสะอาด + ตัดคำ + เตรียม raw_tokens/อนุประโยค
│   ├── clause.py          #  แบ่งอนุประโยคตามคำเชื่อมขัดแย้ง (ระดับ token — กันตัด "ตกแต่ง" ผิด)
│   ├── negation.py        #  จัดการคำปฏิเสธ + แหล่งความจริงเรื่อง "ขั้วของคำ" (word_polarity)
│   ├── sentiment.py       #  จำแนกอารมณ์รีวิว/อนุประโยค + classify_phrase (ราย phrase ตามบริบท)
│   ├── lexicon.py         #  ★ พจนานุกรม: คำนามหัวหมวด, descriptor, idiom, hint, คำพ้อง (เพิ่มคำที่นี่)
│   ├── aspect.py          #  จับหมวดระดับอนุประโยค + route_aspect() ตัวแก้หมวด 4 ชั้น
│   ├── phrases/           #  ★ การสกัดวลีความเห็น (หัวใจของ Review Insight)
│   │   ├── model.py       #     Phrase dataclass (วัตถุที่ไหลผ่านทุกขั้นตอน)
│   │   ├── extract.py     #     สกัดวลี: idiom/MWE → ไวยากรณ์เชิงพจนานุกรม
│   │   ├── quality.py     #     กรองวลีขยะ + คุมการเติมคำนามหัว (กัน insight หลอน)
│   │   ├── canonical.py   #     ทำวลีให้เป็นรูปมาตรฐาน (ตัดคำขยาย/คำเชื่อม)
│   │   ├── synonyms.py    #     รวมวลีความหมายเดียวกันแบบอนุรักษ์นิยม
│   │   └── aggregate.py   #     นับ + จัดอันดับเป็นโครงสร้างของแดชบอร์ด
│   ├── insights.py        #  ★ ข้อสรุปเชิงปฏิบัติ (rule-based, ปรับ threshold ได้)
│   ├── audience_insights.py # มุมผู้บริโภค + แผนงานจัดลำดับสำหรับผู้ประกอบการ
│   ├── export.py          #  ส่งออกผลเป็น CSV / JSON (สำหรับงานวิจัย)
│   └── pipeline.py        #  ร้อยทุกขั้นตอน → ผลลัพธ์ 1 ก้อน (run_analysis)
│
├── db/database.py         # SQLite: ผลวิเคราะห์ + History/Save + สถานะ background job
│
├── templates/             # หน้าเว็บ (Jinja2): base, index, job, dashboard, history, error
├── static/                # css/style.css + js (common/job/dashboard/history)
│
├── data/
│   ├── sample_reviews.json    # ข้อมูลตัวอย่างโหมด demo (30 รีวิว)
│   ├── labeled_reviews.json   # ชุดทดสอบ gold standard ติด label มือ (60 รีวิว)
│   └── settings.json          # ค่าเริ่มต้นเดิม/compatibility; งานใหม่รับตัวเลือกจากแบบฟอร์ม
│
├── eval/                  # การประเมินผลโมเดลอารมณ์ (ดูหัวข้อ "การประเมินผล")
│   ├── evaluate.py        #   คำนวณ Accuracy / F1 / confusion matrix / Cohen's Kappa
│   └── label_tool.py      #   เครื่องมือช่วยติด label เพิ่ม (p/u/n/s/q)
│
├── debug_apify.py         # สคริปต์ตรวจการเชื่อมต่อ Apify
├── docs/superpowers/      # historical archive: spec/plan เก่า ไม่ใช่ source of truth ปัจจุบัน
├── requirements.txt       # เว็บ production/demo (Flask, Waitress, requests, pythainlp)
├── requirements-model.txt # + WangchanBERTa (transformers, torch, ...)
└── .env.example           # ตัวอย่างค่า config
```

จุดที่มัก "ปรับบ่อย":
- **`core/lexicon.py`** → เพิ่มคำนามหัวหมวด / descriptor / idiom / คำพ้อง ให้สกัดวลีครอบคลุมขึ้น
- **`core/insights.py`** → ปรับ threshold / ข้อความข้อเสนอแนะ
- **`static/css/style.css`** → ปรับหน้าตา

---

## 📊 หมวด (Aspect) & ผลลัพธ์

ระบบจัด **3 หมวดหลัก**: **อาหาร (food) / บริการ (service) / บรรยากาศ (ambience)**
โดยเรื่อง **ราคา** ถูกจัดให้อยู่ในหมวด "อาหาร" (เช่น `ราคาไม่แพง`, `ราคาคุ้มค่า`)

`pipeline.run_analysis(url)` คืน dict ที่มีคีย์:

| คีย์ | ความหมาย |
|---|---|
| `store_name`, `source_url`, `total_reviews` | ข้อมูลร้าน + จำนวนรีวิว**ที่วิเคราะห์จริง** (รีวิวไทยหลังคัดกรอง) |
| `fetched_reviews` | จำนวนรีวิว**ที่ดึงมาทั้งหมด** (ก่อนคัดภาษาไทย) — ใช้แสดงความโปร่งใสบนแดชบอร์ด "X จาก Y" |
| `engine` | เครื่องมือที่ใช้จริง (`lexicon (พจนานุกรมคำ)` / `WangchanBERTa`) |
| `distribution` | สัดส่วนอารมณ์รวม (counts + % บวก/กลาง/ลบ) |
| `aspect_summary` | นับอารมณ์ราย aspect (ระดับอนุประโยค) |
| `keywords` | **วลีความเห็นราย aspect/อารมณ์** → แต่ละวลีมี `word`, จำนวน occurrence (`count`), จำนวนรีวิวไม่ซ้ำ (`review_count`) และ `evidence_review_ids` |
| `insights` | ข้อสรุปเชิงปฏิบัติราย aspect พร้อมเหตุผล หลักฐาน และกลยุทธ์ |
| `consumer_summary` | สิ่งที่ควรรู้ก่อนไป, บทสรุปสั้น และข้อควรระวัง |
| `critical_issues` | จุดวิกฤต/เฝ้าระวังจากวลีลบ พร้อมรหัสรีวิวอ้างอิง เหตุผล และกลยุทธ์แนะนำ |
| `operator_plan` | Executive Brief, Strategic Roadmap, Tactical Playbook แยกจุดเสี่ยง/โอกาส และวิธีตรวจผลรอบถัดไป โดยทุกประเด็นเชื่อมกลับไปยังรีวิวหลักฐาน |
| `reviews` | ตารางรีวิวรายรายการ (ข้อความ, ดาว, วันที่, อารมณ์, หมวด) |

---

## 🌐 หน้าเว็บ & API (app.py)

| Method + Route | หน้าที่ |
|---|---|
| `GET /` | หน้าแรก (URL + ตัวเลือกเครื่องมือ/จำนวนรีวิว + ปุ่ม Analyze) |
| `POST /analyze` | ตรวจ URL/โควตา → สร้าง background job → redirect ไปหน้าสถานะ |
| `GET /jobs/<job_id>` | หน้า progress 7 ขั้น; เปิด dashboard อัตโนมัติเมื่อเสร็จ |
| `GET /api/jobs/<job_id>` | status/stage/progress ของ background job เป็น JSON สำหรับ polling |
| `GET /dashboard/<aid>` | ผลวิเคราะห์แบบแท็บผู้บริโภค / ผู้ประกอบการ พร้อม progressive disclosure |
| `GET /history` / `GET /saved` | ประวัติการวิเคราะห์ / รายการโปรด |
| `POST /toggle-save/<aid>` | สลับสถานะรายการโปรด (คืน JSON) |
| `POST /delete/<aid>` | ลบผลวิเคราะห์ (คืน JSON) |
| `GET /api/analysis/<aid>` | คืนผลวิเคราะห์เต็มเป็น JSON |
| `GET /healthz` | readiness ของ SQLite + ความจุ background queue เป็น JSON |
| `GET /settings` / `POST /settings` | route compatibility เดิม; GET พากลับหน้า URL และ UI ใหม่ส่งค่าต่อการวิเคราะห์ |
| `GET /export/<aid>/reviews.csv` | ส่งออกรีวิวรายรายการ (CSV, มี BOM ให้ Excel อ่านไทยถูก) |
| `GET /export/<aid>/summary.csv` | ส่งออกสถิติสรุป (CSV) |
| `GET /export/<aid>/labeling.json` | ส่งออกรีวิวล้วนสำหรับนำไปติด label (JSON) |

มีหน้า error (404/500) ที่เป็นมิตร และครอบ `/analyze` ด้วย error handling เพื่อไม่ให้ผู้ใช้
เจอหน้า 500 ดิบ ๆ เมื่อ Apify/โมเดลขัดข้อง

> ความปลอดภัย: Flask debug ปิดเป็นค่าเริ่มต้น (เปิดด้วย `FLASK_DEBUG=1` เฉพาะตอนพัฒนา);
> `SECRET_KEY` อ่านจาก env ถ้ามี ไม่งั้นสุ่มต่อโปรเซส; POST ทุก route ตรวจ CSRF token;
> session cookie เป็น `HttpOnly`/`SameSite=Lax`; แต่ละเบราว์เซอร์ได้รับ anonymous device token
> แบบสุ่ม 256 บิตใน `HttpOnly` cookie และฐานข้อมูลเก็บเฉพาะ SHA-256 digest ของ token;
> ทุก route ของงาน ผลวิเคราะห์ ประวัติ รายการโปรด การส่งออก และการลบตรวจ owner เดียวกัน;
> มี browser security headers, จำกัด request 1 MiB,
> ตรวจ Google Maps URL แบบแยก hostname/path, ใช้ parameterized SQL และ Jinja2 autoescape
> ระบบไม่มีบัญชีผู้ใช้หรือผู้ดูแลตามขอบเขตของโครงงาน แต่ข้อมูลแต่ละเบราว์เซอร์แยกจากกัน;
> การล้าง cookie หรือใช้โหมดไม่ระบุตัวตนจะเริ่มเป็นอุปกรณ์ใหม่ `/analyze` มี sliding-window
> rate limit ต่อ anonymous device และจำกัดจำนวนงานที่รันพร้อมกัน เพื่อป้องกันการใช้
> Apify/โมเดลเกินโควตา ค่าตั้งต้นคือ 10 ครั้ง/ชั่วโมง/อุปกรณ์, 1 worker และคิวรอ 10 งาน
> ปรับหรือปิด rate limit ได้จาก `.env`

ก่อน deploy หลัง HTTPS ให้กำหนด `SECRET_KEY` แบบยาวและ `SESSION_COOKIE_SECURE=1`
แล้วรัน `python serve.py`; หากต้อง scale หลาย process ควรย้าย worker queue/rate-limit
coordination ไป Redis/Celery/RQ ก่อน เพื่อไม่ให้แต่ละ process มีคิวและโควตาแยกกัน

---

## 🧪 การทดสอบ

มีชุดทดสอบ **314 เทสต์** (ใช้ `unittest` ใน standard library — ไม่ต้องติดตั้ง pytest):

```bash
python -m unittest discover -s tests          # รันทั้งหมด
python -m unittest tests.test_extract_grammar # รันไฟล์เดียว
```

ไฟล์ `.github/workflows/tests.yml` รันชุดเดียวกันอัตโนมัติบน Python 3.12 ทุก push และ pull request
โดยปิด API/model ภายนอก จึงไม่ใช้ token หรือเสียโควตาระหว่าง CI

ครอบคลุม: การสกัดวลี (idiom/ไวยากรณ์/คำปฏิเสธ), การกรองคุณภาพ, การทำรูปมาตรฐาน,
การรวมคำพ้อง, การจัดหมวด 4 ชั้น, อารมณ์รายวลีตามบริบท, phrase evaluation,
CSRF/security headers, settings แบบ atomic, SQLite lifecycle, ขอบเขต Apify response,
มุมมองผู้บริโภค/ผู้ประกอบการ และตัวกรองหลักฐานไม่ให้สร้างเมนูหรือสัญญาณลบผิด
การแยกข้อมูลระหว่าง anonymous devices และสโม้คเทสต์ทั้ง pipeline
(ไม่เรียก API จริงและไม่ขึ้นกับ `.env`)

---

## 📈 การประเมินผลโมเดล (สำหรับบทที่ 4)

ประเมินความแม่นของการจำแนก **อารมณ์** เทียบกับชุดทดสอบที่ติด label มือ
(`data/labeled_reviews.json`, ปัจจุบัน 60 รายการ):

```bash
python eval/evaluate.py                 # ประเมิน engine ปัจจุบัน (demo = lexicon)
USE_MODEL=1 python eval/evaluate.py     # ประเมิน WangchanBERTa จริง
```

ได้: Accuracy, Precision/Recall/F1 รายคลาส, Macro/Weighted-F1, Confusion Matrix และ
Cohen's Kappa — พิมพ์ออกจอ + บันทึก `eval/report.txt`, `eval/confusion_matrix.csv`
(และ `confusion_matrix.png` ถ้ามี matplotlib) คำนวณ metric เองทั้งหมด ไม่พึ่ง scikit-learn

ทดสอบภาษาพูด สแลง ประโยคกลาง และคำปฏิเสธแยกจากคะแนนหลัก:
```bash
python eval/challenge_evaluate.py
python eval/challenge_evaluate.py --engine rule   # ตรวจ fallback แบบไม่โหลดโมเดล
```
ชุด `data/sentiment_challenge_reviews.json` เป็น **curated challenge set 90 ประโยค**
จึงใช้หา edge case เท่านั้นและไม่ถูกรวมกับคะแนน gold standard 60 รีวิว เพื่อไม่ให้ตัวเลข
ดูดีเกินจริง

ขยายชุดทดสอบให้ใหญ่ขึ้น (น่าเชื่อถือกว่า) ด้วยเครื่องมือช่วยติด label:
```bash
python eval/label_tool.py               # ติด label ทีละรีวิว (p/u/n/s/q) ต่อท้ายไฟล์ gold
python -m eval.build_sentiment_queue --target 300  # เตรียมรีวิวจริงในเครื่องสำหรับติด label
```

ขั้นตอนทำวิจัยแบบครบวงจร: วิเคราะห์ร้านจริง → Export "รีวิวสำหรับติด label (JSON)"
→ `label_tool.py` ติด label จากข้อมูลจริง → `evaluate.py` วัด F1

### ประเมินการสกัดวลีระดับ Span

ระบบมี workflow แยกสำหรับสร้าง gold set โดยผู้ติด label 2 คน วัด agreement,
adjudicate และประเมิน Exact/Partial span + Aspect/Sentiment/Joint F1:

```bash
python -m eval.build_phrase_queue --seed 2026
python -m eval.phrase_label_tool --annotator annotator_a
python -m eval.phrase_label_tool --annotator annotator_b
python -m eval.phrase_agreement data/phrase_annotations_annotator_a.json data/phrase_annotations_annotator_b.json
python -m eval.phrase_adjudicate data/phrase_annotations_annotator_a.json data/phrase_annotations_annotator_b.json
python -m eval.phrase_dataset data/phrase_gold.json --split-dir data/phrase_splits
python -m eval.phrase_evaluate data/phrase_gold.json --engine rule
python -m eval.phrase_evaluate data/phrase_gold.json --engine llm --llm-batch-size 25
python -m eval.phrase_error_analysis data/phrase_gold.json --engine rule
```

รายละเอียดเกณฑ์อยู่ใน `docs/PHRASE-ANNOTATION-GUIDE.md` คิวปัจจุบันสร้างจากข้อมูลในเครื่อง
ได้ 167 รีวิวไม่ซ้ำ และถูก ignore จาก Git จนกว่าจะผ่านการตรวจสิทธิ์ข้อมูล/การ adjudicate

---

## ⚠️ ข้อจำกัด (Limitations)

- แบ่งอนุประโยคเฉพาะคำเชื่อมขัดแย้งกลุ่ม "แต่" (อนุรักษ์นิยม เพื่อกันการแบ่งผิด)
- การสกัดวลีเป็นแบบ **อิงพจนานุกรม (lexicon-driven)** — คำที่ไม่อยู่ใน `core/lexicon.py`
  เช่น คำสแลงใหม่ ๆ จะไม่ถูกจับ (ระบบไม่ได้เรียนรู้คำใหม่เอง); วิธีปรับปรุงคือ
  **เพิ่มคำเข้า `core/lexicon.py` ด้วยมือ**
- ขอบเขตคำปฏิเสธมองเฉพาะคำขั้วที่ติดกัน 1 คำ
- มี framework ประเมินวลีเชิงปริมาณแล้ว แต่ gold set ยังต้องติด label อิสระ 2 คนและ adjudicate;
  ห้ามใช้ตัวเลข phrase F1 จนกว่ากระบวนการนี้จะเสร็จ
- การวิเคราะห์จริง 1 ครั้งอาจใช้เวลาหลายสิบวินาทีถึงไม่กี่นาที (รอ Apify + โมเดลบน CPU)

---

## หมายเหตุ

- ฐานข้อมูล `insightreview.db` ถูกสร้างอัตโนมัติเมื่อรันครั้งแรก
- โหมด demo ออกแบบให้ทดสอบ UI/flow ได้โดยไม่มีค่าใช้จ่ายและไม่ต้องต่อเน็ตหนัก
- เอกสารออกแบบเชิงลึกของฟีเจอร์สกัดวลีอยู่ที่ `docs/superpowers/` (spec + plan)
