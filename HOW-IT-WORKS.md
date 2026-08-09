# InsightReview — คู่มือเข้าใจระบบทั้งหมด (ตั้งแต่ต้นจนจบ)

เอกสารนี้อธิบายว่าเว็บทำงานยังไง "ทุกซอกทุกมุม" — กดปุ่มเดียวแล้วเกิดอะไรขึ้นบ้าง
ไล่จากไฟล์ไหน โค้ดตรงไหน จนได้ผลบนหน้าจอ

---

## 0) ภาพรวม 30 วินาที

InsightReview = เว็บวิเคราะห์รีวิวร้านอาหารจาก Google Maps เป็นภาษาไทย
- **รับ**: ลิงก์ร้านจาก Google Maps
- **ทำ**: ดึงรีวิว → คัดเฉพาะไทย → วิเคราะห์อารมณ์ (บวก/กลาง/ลบ) → แยกหมวด (อาหาร/บริการ/บรรยากาศ) → สกัดคำสำคัญ → สรุปเป็นข้อเสนอแนะ
- **แสดง**: แดชบอร์ด 2 แท็บ — "สำหรับผู้บริโภค" และ "สำหรับผู้ประกอบการ"

**เทคโนโลยี**
| ชั้น | ใช้อะไร |
|------|---------|
| เว็บเซิร์ฟเวอร์ | Flask (Python) + เทมเพลต Jinja2 |
| หน้าเว็บ | HTML/CSS + JavaScript ล้วน (ไม่มี framework, ไม่มี build) |
| ฐานข้อมูล | SQLite (ไฟล์ `insightreview.db`) |
| ดึงรีวิว | Apify (โหมดจริง) หรือไฟล์ตัวอย่าง (โหมด demo) |
| วิเคราะห์อารมณ์ | WangchanBERTa (AI) หรือ Lexicon (พจนานุกรมคำ) |
| เรียบเรียงเนื้อหา AI | Google Gemini (ถ้ามี key) หรือ rule-based |

---

## 1) แผนที่ไฟล์ (ใครทำหน้าที่อะไร)

```
app.py                 ← หัวใจฝั่งเซิร์ฟเวอร์: ทุก URL/route อยู่ที่นี่
config.py              ← ตั้งค่ากลาง อ่าน .env, โหมด demo/จริง, ค่าที่ผู้ใช้ปรับได้

core/                  ← ตรรกะการวิเคราะห์ทั้งหมด (เรียงตามลำดับ pipeline)
  scraper.py           ← ขั้น 1: ดึงรีวิว (Apify / ไฟล์ตัวอย่าง)
  preprocess.py        ← ขั้น 2: คัดไทย + ล้างข้อความ + ตัดคำ + แบ่งอนุประโยค
  clause.py            ← เครื่องมือย่อย: แบ่งประโยคที่ "แต่"
  negation.py          ← เครื่องมือย่อย: จัดการคำปฏิเสธ "ไม่อร่อย"
  sentiment.py         ← ขั้น 3: จำแนกอารมณ์ (โมเดล/lexicon)
  aspect.py            ← ขั้น 4: จับหมวด + สรุปอารมณ์ราย aspect
  lexicon.py           ← พจนานุกรมกลาง (คำหมวด/คำขั้ว/idiom/คำเชื่อม)
  phrases/             ← ขั้น 5: สกัด "วลีความเห็น" เป็นคำสำคัญ
    model.py           ←   โครงข้อมูล Phrase ที่ไหลผ่านทุก stage
    extract.py         ←   stage 1: จับวลีจากไวยากรณ์ (P1–P7 + idiom)
    quality.py         ←   stage 2: กรองวลีคุณภาพ + เดา aspect ชั่วคราว
    canonical.py       ←   stage 3: สร้างคีย์รวม + ข้อความแสดงผล
    synonyms.py        ←   stage 4: รวมคำพ้องความ (whitelist)
    aggregate.py       ←   stage 7: นับความถี่ → คำสำคัญ top 6 ต่อหมวด/อารมณ์
    llm_extract.py     ←   ทางเลือก: ใช้ Gemini สกัดวลีแทน rule-based
  insights.py          ← ขั้น 5b: สร้างข้อสรุป rule-based ต่อ aspect
  practical_rules.py   ← ขั้น 5c: เรื่องที่ควรรู้ก่อนไปจากกฎ + รีวิวอ้างอิง
  narrative.py         ← ขั้น 5d: เรียบเรียงเนื้อหา 2 แท็บ (Gemini + fallback)
  pipeline.py          ← ★ ร้อยทุกขั้นเข้าด้วยกัน = run_analysis()
  export.py            ← ทำไฟล์ CSV/JSON ส่งออก (งานวิจัย)

db/
  database.py          ← เก็บ/อ่านผลวิเคราะห์ลง SQLite

templates/             ← หน้าเว็บ (Jinja2)
  base.html            ←   โครงร่วม: sidebar + topbar + toast/loading/modal
  index.html           ←   หน้าแรก: ช่องวางลิงก์ + ปุ่ม Analyze
  dashboard.html       ←   ★ หน้าแสดงผล 2 แท็บ
  history.html         ←   หน้าประวัติ / รายการโปรด (ใช้ร่วมกัน)
  error.html           ←   หน้า 404/500
  _model_picker.html   ←   ชิ้นส่วนตัวเลือกโมเดล (ฝังในฟอร์ม Analyze)

static/
  css/style.css        ←   สไตล์ทั้งเว็บ (มี design token :root)
  js/common.js         ←   ยูทิลร่วม: toast, modal, loading, ตัวเลือกโมเดล
  js/dashboard.js      ←   พฤติกรรมหน้าแดชบอร์ด (สลับแท็บ/กรอง/แสดงเพิ่ม/save)
  js/history.js        ←   พฤติกรรมหน้าประวัติ (ค้นหา/ลบ)

data/
  sample_reviews.json  ←   รีวิวตัวอย่างสำหรับโหมด demo
  labeled_reviews.json ←   ชุดทดสอบติด label (ไว้วัดความแม่น)
  settings.json        ←   ค่าที่ผู้ใช้ปรับ (สร้างอัตโนมัติ, gitignore)

tests/                 ← ชุดทดสอบ 135 ตัว (pytest)
eval/, scripts/        ← เครื่องมือ "วัดผล/เทียบเครื่องยนต์" (งานวิจัย ไม่ใช่รันเว็บ)
output/                ← ไฟล์วิทยานิพนธ์ PDF/HTML (ผลงาน — ห้ามลบ)
docs/                  ← เอกสารประกอบ + แผนออกแบบ
```

---

## 2) ระบบเริ่มทำงานยังไง (ตอนสั่ง `python app.py`)

1. **import config** → `config.py` รัน `_load_dotenv()` อ่านไฟล์ `.env` ใส่เข้า
   environment (APIFY_TOKEN, GEMINI_API_KEY, USE_MODEL, ฯลฯ) — env จริงมาก่อน .env เสมอ
2. สร้าง Flask app + ตั้ง `secret_key` (สำหรับ flash message)
3. `database.init_db()` → สร้างตาราง `analysis` ถ้ายังไม่มี
4. `inject_globals()` (context processor) → ทำให้ **ทุกหน้า** เข้าถึง
   `demo_mode`, `user_settings`, `review_caps` ได้โดยไม่ต้องส่งเอง
5. `app.run(port=config.PORT)` → เปิดเว็บที่พอร์ต 5000
   > ⚠️ macOS: พอร์ต 5000 ชนกับ AirPlay → รันด้วย `PORT=5001 python app.py`

---

## 3) เส้นทางคำขอทั้งหมด (ทุก URL ใน `app.py`)

| Method + URL | ทำอะไร |
|--------------|--------|
| `GET /` | หน้าแรก (ช่องวางลิงก์) → `index.html` |
| `POST /analyze` | ★ รับ URL → รัน pipeline → เก็บ DB → เด้งไป dashboard |
| `GET /dashboard/<id>` | แสดงผลวิเคราะห์ → `dashboard.html` |
| `GET /history` | ประวัติทั้งหมด |
| `GET /saved` | รายการโปรด |
| `POST /toggle-save/<id>` | สลับบันทึกโปรด (คืน JSON) |
| `POST /delete/<id>` | ลบผลวิเคราะห์ (คืน JSON) |
| `POST /regenerate/<id>` | ★ สร้างเนื้อหา AI ใหม่จากข้อมูลเดิม (ไม่ดึงรีวิวซ้ำ) |
| `GET /api/analysis/<id>` | คืนผลเป็น JSON ดิบ |
| `GET /export/<id>/reviews.csv` | ดาวน์โหลดรีวิว CSV |
| `GET /export/<id>/summary.csv` | ดาวน์โหลดสรุป CSV |
| `GET /export/<id>/labeling.json` | ดาวน์โหลดรีวิวไว้ติด label |
| `GET /settings` | (เลิกใช้) redirect กลับหน้าแรก — ตัวเลือกย้ายไปช่องลิงก์แล้ว |
| `POST /settings` | ยังรับบันทึกค่าได้ (backward-compat) |

---

## 4) ★ หัวใจ: กด Analyze แล้วเกิดอะไรขึ้น (ทีละสเต็ป)

### 4.1 ฝั่งหน้าเว็บ (`index.html` + `common.js`)
- ผู้ใช้วางลิงก์ในฟอร์ม `<form id="analyzeForm" action="/analyze" method="post">`
- ในฟอร์มมี `_model_picker.html` = ช่องซ่อน `engine`, `extract_engine`, `max_reviews`
  (ค่าเริ่มจาก `user_settings`; `common.js → initModelPickers()` คอยอัปเดตเมื่อผู้ใช้เลือก)
- กด Analyze → JS โชว์ loading overlay → ส่ง POST ไป `/analyze`

### 4.2 ฝั่งเซิร์ฟเวอร์ (`app.py → analyze()`)
1. อ่าน `url` จากฟอร์ม
2. ถ้าเป็นโหมดจริง (มี Apify token) → ตรวจว่า URL ว่างไหม + เป็นลิงก์ Maps ไหม
   (`_looks_like_maps_url`) ไม่ผ่าน → flash เตือน + กลับหน้าแรก
3. `_persist_picked_engines(request.form)` → บันทึกตัวเลือกโมเดล/สกัดคำ/จำนวนรีวิว
   ที่เลือกจากช่องลิงก์ ลง `settings.json`
4. `pipeline.run_analysis(url)` ← **งานหลักทั้งหมดอยู่ในนี้** (ดูข้อ 4.3)
   ครอบด้วย try/except: ถ้าพัง → flash เตือน ไม่ให้เจอหน้า 500 ดิบ
5. ถ้าไม่มีรีวิวไทยเลย (`total_reviews == 0`) → flash เตือน + กลับหน้าแรก
6. `database.save_analysis(result)` → เก็บลง DB คืน `id`
7. `redirect(/dashboard/<id>)` → เด้งไปหน้าแสดงผล

### 4.3 ★★ `pipeline.run_analysis()` — 6 ขั้นตอน

```
URL
 │
 ├─(1) scraper.fetch_reviews(url)            → รีวิวดิบ + ชื่อร้าน
 │        โหมดจริง: เรียก Apify actor "compass/google-maps-reviews-scraper"
 │        โหมด demo: อ่าน data/sample_reviews.json
 │
 ├─(2) preprocess.filter_and_prepare(reviews) → รีวิวไทยที่สะอาดแล้ว
 │        • is_thai()      คัดเฉพาะไทย (≥20% เป็นอักษรไทย) + ตัดรีวิวซ้ำ
 │        • clean_text()   ลบ URL/อีโมจิ/สัญลักษณ์, "อร่อยยยย"→"อร่อย"
 │        • tokenize()     ตัดคำด้วย PyThaiNLP (newmm)
 │        • negation       รวม "ไม่"+"อร่อย" → "ไม่อร่อย" (ก่อนลบ stopword)
 │        • clause.split   แบ่งอนุประโยคที่ "แต่/แต่ว่า/อย่างไรก็ตาม"
 │        คืนแต่ละรีวิวเป็น dict: text, rating, clean, tokens, tokens_base, clauses[]
 │        (มี token 3 มุมมอง: tokens=รวม negation+ตัด stopword / tokens_base=ตัด
 │         stopword ไม่รวม negation / raw_tokens=ดิบทั้งหมด — แต่ละ stage ใช้ต่างกัน)
 │
 ├─(3) sentiment.analyze_all(reviews)         → ใส่ 'sentiment' ให้ทุกรีวิว+ทุก clause
 │        เลือกเครื่องยนต์จาก config.USE_MODEL:
 │        • WangchanBERTa (AI): โมเดล wisesight 4 คลาส (map question→neutral)
 │        • Lexicon: นับคำบวก/ลบจากพจนานุกรม (เข้าใจ negation ผ่าน word_polarity)
 │        ตั้งอารมณ์ 2 ระดับ: ระดับรีวิว (โดนัท/ตาราง) + ระดับ clause (สรุปราย aspect)
 │
 ├─(4) aspect.tag_aspects + aspect_sentiment_summary → อารมณ์แยกหมวด
 │        • detect_aspects: จับว่า clause พูดถึงหมวดไหน (ตรงคำใน ASPECT_LEXICON)
 │        • นับอารมณ์ "ตาม clause" ไม่ broadcast ทั้งรีวิว
 │          → "อาหารอร่อยแต่บริการช้า": อาหาร=บวก, บริการ=ลบ (ไม่ปนกัน)
 │        คืน {food:{pos,neu,neg,total}, service:{...}, ambience:{...}}
 │
 ├─(5) _phrase_pipeline(reviews) → keyword ต่อหมวด/อารมณ์ (7 stages ย่อย)
 │        rule-based (ค่าเริ่ม) หรือ Gemini (ถ้าตั้ง extract_engine=llm)
 │        stage1 extract → stage2 quality → stage3 canonical → stage4 synonyms
 │        → route_aspect (จับหมวดวลี) → stage6 classify (อารมณ์วลี) → stage7 aggregate
 │        คืน {food:{positive:[{word,count}], neutral:[...], negative:[...]}, ...}
 │        (รายงาน engine ที่ "ทำงานจริง" — ถ้า Gemini ล้ม/โควตาหมด จะเป็น "rule")
 │
 ├─(5b) insights.generate_insights(summary, keywords) → ข้อสรุป rule-based ต่อหมวด
 │        เกณฑ์: บวก≥65%=จุดแข็ง / ลบ≥30%=ควรปรับปรุง / ต้องมี≥5 รีวิวถึงสรุป
 │
 ├─(5c) practical_rules.enrich_result({...}) → ข้อมูลวางแผนก่อนไปที่ตรวจสอบได้
 │        จัดกลุ่มคิว/ที่จอด/ราคา/การเดินทาง/ข้อจำกัด พร้อม review_id อ้างอิง
 │
 ├─(5d) narrative.build({...}) → เนื้อหา 2 แท็บ (Gemini เรียบเรียง / rule-based)
 │        consumer: tl_dr, top_mentions, things_to_know, warnings
 │        entrepreneur: critical_points, actionable_insights (What/Why/How)
 │        โดย things_to_know ถูก sync จาก practical_rules เสมอ ไม่ให้ AI แต่งใหม่
 │
 └─(6) ประกอบผลลัพธ์เป็น dict เดียว (ดูข้อ 5) → คืนให้ analyze() เก็บ DB
```

### 4.4 ขยาย: ขั้น 5 การสกัดวลี (7 stage) — ไฟล์ `core/phrases/`
1. **extract.py** — จับวลีจากไวยากรณ์ (ไม่ใช้ POS เพราะไม่แม่นกับรีวิวไทย):
   idiom/คำประสม (MWE) ก่อน แล้วรูปแบบ P1–P7 เช่น `อาหาร+อร่อย` (P1), `รอ+นาน`→"รอนาน" (P3), `ไม่+ประทับใจ` (P7)
2. **quality.py** — ทิ้งวลีคุณภาพต่ำ (เช่นมีแต่คำกริยา "ชอบ/แนะนำ") + เดา aspect ชั่วคราวให้วลีที่มีแต่คำบรรยาย
3. **canonical.py** — สร้าง `canonical`/`agg_key` (คีย์รวม ตัดคำเน้น) แยกจาก `display` (คำที่โชว์จริง เก็บ "มาก")
4. **synonyms.py** — รวมคำพ้องความเฉพาะที่อยู่ใน whitelist `MEMBER_TO_CONCEPT`
5. **route_aspect** (aspect.py) — จับหมวดของวลี 4 ชั้น: idiom → คำนามหลัก → บริบท clause → คำใบ้
6. **sentiment.classify_phrase** — อารมณ์ของวลี: ถ้าวลีมีขั้วชัดในตัว ("ราคาแพง") ใช้ขั้วนั้น ไม่งั้นยืมอารมณ์ของ clause
7. **aggregate.py** — นับความถี่ → คืน top 6 ต่อ (หมวด × อารมณ์)

---

## 5) รูปแบบข้อมูลผลลัพธ์ (Data Contract)

`run_analysis()` คืน dict นี้ ซึ่งถูกเก็บทั้งก้อนใน DB และส่งให้หน้าเว็บ:

```jsonc
{
  "store_name": "ครัวบ้านสวน",
  "source_url": "https://maps.google.com/...",
  "total_reviews": 30,          // รีวิวไทยที่วิเคราะห์จริง
  "fetched_reviews": 45,        // ดึงมาทั้งหมด (ก่อนคัดไทย)
  "engine": "WangchanBERTa",    // เครื่องยนต์อารมณ์ที่ใช้จริง
  "extract_engine": "rule",     // เครื่องยนต์สกัดวลีที่ใช้จริง
  "narrative": {                // ← เนื้อหา 2 แท็บ (ข้อ 9)
    "engine": "gemini",         //   หรือ "rule"
    "consumer": { "tl_dr", "top_mentions", "things_to_know", "warnings" },
    "entrepreneur": { "critical_points", "actionable_insights" }
  },
  "practical_insights": [       // ข้อมูลก่อนไปจากกฎ พร้อมหลักฐาน
    {"topic", "title", "advice", "status", "evidence_review_ids"}
  ],
  "practical_insights_meta": {"topic_count", "evidence_review_count"},
  "distribution": { "counts": {...}, "total": 30, "pct": {...} },  // %รวม 100 เป๊ะ
  "aspect_summary": { "food": {...}, "service": {...}, "ambience": {...} },
  "keywords": { "food": {"positive":[{word,count}], ...}, ... },
  "insights": [ {aspect, level, message, ...} ],   // ข้อสรุป rule-based
  "reviews": [ {review_id, text, rating, review_date, sentiment, aspects} ]
}
```

---

## 6) เก็บ/อ่านข้อมูล (`db/database.py`)

- ตารางเดียว `analysis`: เก็บคอลัมน์ค้นหาบ่อย (store_name, %, is_saved) + **`payload`
  = ผลทั้ง dict เป็น JSON** (ออกแบบให้ง่าย ไม่ต้องแตกหลายตาราง)
- `save_analysis(result)` → INSERT คืน id
- `get_analysis(id)` → อ่าน payload กลับมา + เติม `id`, `is_saved`
- `update_narrative(id, narrative)` → อัปเดต **เฉพาะ** ฟิลด์ narrative (ใช้ตอน regenerate)
- `toggle_saved / delete_analysis / list_analyses / list_saved`
> เพราะ payload เก็บทั้ง dict การเพิ่มฟิลด์ใหม่ (เช่น `narrative`) จึง **ไม่ต้องแก้ schema**

---

## 7) หน้าเว็บแสดงผลยังไง (`dashboard.html` + `dashboard.js`)

`base.html` เป็นโครงร่วม (sidebar เมนู + topbar + ระบบ toast/loading/modal)
ทุกหน้า `extends` จากมัน

**`dashboard.html` แบ่ง 2 แท็บ** (สลับด้วยปุ่ม `.vtab` → `dashboard.js`):

**แท็บผู้บริโภค** (ผสาน `a.narrative.consumer` กับ `a.practical_insights`)
- Narrative ดูแล TL;DR · จุดเด่นที่ลูกค้าชอบ · ข้อควรระวัง
- Practical rules ดูแล “เรื่องที่ควรรู้ก่อนไป” พร้อมสถานะ คำแนะนำ และรหัสรีวิวอ้างอิง
- เมื่อไม่มี narrative เก่า ระบบยังคำนวณ practical rules ตอนเปิดหน้าได้

**แท็บผู้ประกอบการ**
- การ์ด % + โดนัท (CSS conic-gradient ล้วน ไม่ใช้ JS วาด)
- 🚨 จุดวิกฤต (แดง) จาก `narrative.entrepreneur.critical_points`
- Analysis result: โชว์ 6 รีวิวแรก + ปุ่ม "แสดงเพิ่มเติม" (`dashboard.js`, CAP=6),
  สลับ All/Keywords, กรองตามอารมณ์
- ข้อเสนอแนะ What/Why/How จาก `actionable_insights`

**Banner "สร้างเนื้อหา AI ใหม่"** — ขึ้นเมื่อ `narrative.engine != 'gemini'`
กดแล้ว `dashboard.js` ยิง `POST /regenerate/<id>` แล้ว reload

`dashboard.js` คุม: สลับแท็บ, All/Keywords, กรองอารมณ์+แสดงเพิ่มเติม (รวมกันใน
`renderReviews()`), ปุ่ม save/export, ปุ่ม regenerate

---

## 8) โหมด demo vs โหมดจริง + ตัวเลือกผู้ใช้

**ควบคุมที่ `config.py`** (อ่านจาก `.env`):
- `APIFY_TOKEN` ว่าง → **โหมด demo** (ใช้ `data/sample_reviews.json`, ไม่ต้องใส่ URL)
- ตั้ง `APIFY_TOKEN` → **โหมดจริง** (ดึงจาก Google Maps ผ่าน Apify)

**ตัวเลือกที่ผู้ใช้ปรับได้** (อยู่ในช่องวางลิงก์ = `_model_picker.html` แล้ว):
- `engine`: WangchanBERTa (แม่น) / Lexicon (เร็ว)
- `extract_engine`: Rule-based (ออฟไลน์) / Gemini (ฉลาดขึ้น)
- `max_reviews`: จำนวนรีวิว (บีบอยู่ในเพดาน `MIN_REVIEWS`–`MAX_REVIEWS_CAP`)
ทั้งหมดบันทึกลง `data/settings.json` ผ่าน `config.save_settings()` มีผลทันที

---

## 9) AI (Gemini) ทำงานยังไง (`core/narrative.py`)

- `build(core)`:
  - ถ้า `available()` (มี key + SDK) → เรียก Gemini แบบ **มี retry** เมื่อโดน
    rate-limit ชั่วคราว (`_generate`), บังคับ JSON ตาม schema, แล้ว `_sanitize`
  - ถ้า Gemini ล้ม/โควตาหมด (429) → ตกไป `_fallback()` = **rule-based**
    (สร้าง TL;DR/warnings/What-Why-How จากคีย์เวิร์ด + ตัวช่วยธีม `_FIX_HINTS`)
  - ไม่ว่า Gemini หรือ fallback จะทำงาน `things_to_know` จะถูก sync จาก
    `practical_rules` ชุดเดียวเสมอ จึงไม่ขัดกับการ์ดหลักฐานบน Dashboard
  - ติดป้าย `engine: "gemini"` หรือ `"rule"` เสมอ (โปร่งใส ไม่โม้)
- **ปุ่ม Regenerate** (`/regenerate/<id>`): ใช้ข้อมูลที่เก็บใน DB สร้าง narrative ใหม่
  โดย **ไม่ดึงรีวิว/รัน pipeline ซ้ำ** → ประหยัดโควตา Gemini + เครดิต Apify
  (วิเคราะห์ตอนโควตาหมดได้ rule-based ไว้ก่อน พอโควตารีเซ็ตค่อยกดอัปเกรด)
> Gemini เป็นแค่ "ชั้นเรียบเรียงภาษา" ทับผลวิเคราะห์ของ pipeline — ตัววิเคราะห์จริง
> ยังเป็น WangchanBERTa + rule-based ของระบบเอง

---

## 10) แผนผังลำดับแบบย่อ

```
[เบราว์เซอร์]  กด Analyze (index.html)
     │ POST /analyze  (url + engine + extract_engine + max_reviews)
     ▼
[app.py analyze()]  ตรวจ URL → บันทึกตัวเลือก → pipeline.run_analysis()
     │
     ▼
[pipeline] scraper → preprocess → sentiment → aspect → phrases
                    → insights → practical rules → narrative → รวมเป็น result dict
     │
     ▼
[database.save_analysis]  เก็บลง SQLite → คืน id
     │
     ▼  redirect
[app.py dashboard()]  database.get_analysis(id) → render dashboard.html
     │
     ▼
[เบราว์เซอร์]  แสดง 2 แท็บ + dashboard.js คุมการโต้ตอบ
                (กด "สร้างเนื้อหา AI ใหม่" → POST /regenerate/<id> → reload)
```

---

## 11) ไฟล์ไหนจำเป็น / ลบได้

| ไฟล์/โฟลเดอร์ | หน้าที่ | ลบได้? |
|--------------|---------|--------|
| `app.py`, `config.py`, `core/`, `db/`, `templates/`, `static/`, `data/` | รันเว็บ | ❌ ห้ามลบ |
| `tests/` | ชุดทดสอบ 135 ตัว | ⚠️ เก็บไว้ (ยืนยันระบบไม่พัง) |
| `scripts/compare_engines.py` | เทียบ rule vs Gemini | ❌ ผูกกับ `test_compare_engines.py` |
| `eval/` (`evaluate.py`, `label_tool.py`) | เครื่องมือวัดความแม่น (F1) | ⚠️ งานวิจัย — เก็บไว้ทำวิทยานิพนธ์ |
| `eval/*.png/*.csv/report.txt` | ผลวัดที่ generate แล้ว | 🟡 ลบได้ (สร้างใหม่ได้จาก evaluate.py) |
| `output/*.pdf`, `*.html` | ★ ไฟล์วิทยานิพนธ์ | ❌ ห้ามลบเด็ดขาด |
| `docs/RESEARCH-GUIDE.md`, `ANALYSIS.md` | เอกสารประกอบ | ⚠️ เก็บไว้ |
| `docs/superpowers/` | แผน/สเปกตอนพัฒนา | 🟡 ลบได้ถ้าไม่อ้างอิงแล้ว |
| `debug_apify.py` | สคริปต์ debug Apify แยกเดี่ยว | 🟡 ลบได้ (ไม่มีใครเรียก) |
| `__pycache__/`, `*.pyc` | cache Python | ✅ ลบได้ (สร้างใหม่เอง) — จัดการให้แล้ว |
| `.venv/` (1.3GB) | virtualenv | 🟡 ลบได้แต่ต้อง `pip install` ใหม่ก่อนรัน |
| `insightreview.db` | ประวัติที่บันทึกไว้ | 🟡 ลบ = ล้างประวัติ (สร้างใหม่อัตโนมัติ) |
| `.env` | เก็บ token/key ลับ | ❌ ห้ามลบ/ห้าม commit |

**ลบไปแล้วรอบก่อน**: `frontend/` (Vue SPA ที่ไม่ใช้), `templates/settings.html`

---

## 12) วิธีรัน

```bash
# ครั้งแรก: ติดตั้ง dependency (ถ้ายังไม่มี .venv)
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt          # + requirements-model.txt ถ้าใช้ WangchanBERTa

# รันเว็บ (macOS ใช้ 5001 เพราะ 5000 ชนกับ AirPlay)
PORT=5001 .venv/bin/python3.11 app.py
# เปิด http://127.0.0.1:5001

# รันทดสอบ
.venv/bin/python3.11 -m pytest -q
```

> ⚠️ โค้ดใช้ syntax Python 3.10+ (`str | None`) — ต้องรันด้วย **python3.11**
> (ตัว `.venv/bin/python` เป็น 3.9 จะ error)
