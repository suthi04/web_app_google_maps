# คู่มือทำวิจัยฉบับสมบูรณ์ — InsightReview

> **วัตถุประสงค์ของเอกสารนี้:** รวมทุกอย่างที่ต้องรู้เพื่อ "เขียนเล่ม + ทำการทดลอง + สอบป้องกัน" วิทยานิพนธ์
> เรื่อง *เว็บแอปเปลี่ยนรีวิวร้านอาหารจาก Google Maps ให้กลายเป็นกลยุทธ์ทางธุรกิจ*
> ทุกตัวเลข/คำกล่าวอ้างในเอกสารนี้ตรวจจากโค้ดจริง (branch `feat/review-insight-phrase-extraction`, 2026-06-12)
> ไม่มีการคาดเดา — จุดที่เป็นความเห็น/ข้อควรระวังจะระบุชัด
>
> อ่านคู่กับ: [ANALYSIS.md](ANALYSIS.md) (วิเคราะห์ repo เชิงลึก) · [../README.md](../README.md) (วิธีรัน) ·
> `output/InsightReview-Thesis-v100.pdf` (ร่างเล่มฉบับสมบูรณ์) · `output/InsightReview-Review-Summary.pdf` (รายงานตรวจสอบ)

---

## สารบัญ
1. [สรุปงานวิจัยใน 1 หน้า](#1-สรุปงานวิจัยใน-1-หน้า)
2. [สถาปัตยกรรมและไปป์ไลน์จริง](#2-สถาปัตยกรรมและไปป์ไลน์จริง)
3. [วิธีการเชิงเทคนิคแบบละเอียด (สำหรับเขียนบทที่ 3)](#3-วิธีการเชิงเทคนิคแบบละเอียด-สำหรับเขียนบทที่-3)
4. [ชุดข้อมูล: ที่มา โครงสร้าง การขยาย](#4-ชุดข้อมูล-ที่มา-โครงสร้าง-การขยาย)
5. [การทดลองและการประเมินผล (สำหรับบทที่ 4)](#5-การทดลองและการประเมินผล-สำหรับบทที่-4)
6. [วิธีรันระบบครบทุกโหมด](#6-วิธีรันระบบครบทุกโหมด)
7. [การขยายพจนานุกรม (lexicon)](#7-การขยายพจนานุกรม-lexicon)
8. [ผลปัจจุบันและการตีความ](#8-ผลปัจจุบันและการตีความ)
9. [ข้อจำกัดและสิ่งที่ต้องระวังในห้องสอบ](#9-ข้อจำกัดและสิ่งที่ต้องระวังในห้องสอบ)
10. [เช็กลิสต์สิ่งที่ต้องทำก่อนส่งเล่ม](#10-เช็กลิสต์สิ่งที่ต้องทำก่อนส่งเล่ม)
11. [คลังคำถามกรรมการ + คำตอบตัวอย่าง](#11-คลังคำถามกรรมการ--คำตอบตัวอย่าง)
12. [ตารางอ้างอิงคำกล่าวอ้าง → ไฟล์โค้ด (Claim ↔ Evidence)](#12-ตารางอ้างอิงคำกล่าวอ้าง--ไฟล์โค้ด-claim--evidence)
13. [แผนการดำเนินงาน (Gantt) และการ map กับบทในเล่ม](#13-แผนการดำเนินงาน-gantt-และการ-map-กับบทในเล่ม)
14. [อภิธานศัพท์ (Glossary EN–TH)](#14-อภิธานศัพท์-glossary-enth)
15. [บรรณานุกรมและการอ้างอิง](#15-บรรณานุกรมและการอ้างอิง)

---

## 1. สรุปงานวิจัยใน 1 หน้า

| หัวข้อ | เนื้อหา |
|---|---|
| **ชื่อเรื่อง** | เว็บแอปเปลี่ยนรีวิวร้านอาหารจาก Google Maps ให้กลายเป็น "กลยุทธ์" ทางธุรกิจ |
| **ปัญหา** | รีวิวไทยบน Google Maps เยอะ ไม่มีโครงสร้าง วิเคราะห์มือยาก + ภาษาไทยมีสแลง/ยืดเสียง/ปฏิเสธที่พลิกความหมาย |
| **วัตถุประสงค์ 1** | ประยุกต์ NLP จำแนกอารมณ์ + **สกัดวลีความเห็นเชิงหมวด** จากรีวิว |
| **วัตถุประสงค์ 2** | พัฒนาเว็บแดชบอร์ด + ข้อเสนอแนะเชิงปฏิบัติ เพื่อสนับสนุนการตัดสินใจ |
| **Contribution หลัก** | สกัด "วลี" ที่นำไปใช้ได้ (เช่น `ราคาไม่แพง`, `รอนาน`) ไม่ใช่ "คำเดี่ยว" + ทำงานระดับอนุประโยค + จัดการคำปฏิเสธ |
| **เทคโนโลยี** | Python, Flask, HTML/CSS/JS, SQLite, Apify, PyThaiNLP, WangchanBERTa, Gemini (ทางเลือก) |
| **ผลการประเมิน** | จำแนกอารมณ์ (WangchanBERTa): Accuracy 88.3%, Macro-F1 0.879, Kappa 0.825 (n=60) |
| **กลุ่มเป้าหมาย** | เจ้าของร้านอาหาร (หลัก, B2B), ผู้บริโภคทั่วไป |

**ประโยคขายงาน (ใช้ตอบกรรมการ):** *"งานวิจัยนี้ไม่ได้แค่บอกว่ารีวิวบวกกี่เปอร์เซ็นต์ แต่บอกว่า 'ด้านไหน' เป็นจุดแข็ง/จุดอ่อน
และลูกค้าพูดถึง 'ด้วยถ้อยคำใด' แล้วแปลงเป็นข้อเสนอแนะที่ผู้ประกอบการลงมือทำได้จริง"*

---

## 2. สถาปัตยกรรมและไปป์ไลน์จริง

```
ผู้ใช้กรอก URL
   │
   ▼ core/scraper.py        ดึงรีวิว: Apify (จริง) / sample_reviews.json (demo)
   ▼ core/preprocess.py     คัดเฉพาะไทย (is_thai≥0.2) + ลบ noise + normalize ยืดเสียง + ตัดคำ (newmm)
   │                        + แบ่งอนุประโยค (clause) + จัดการคำปฏิเสธ → สร้าง 3 token views
   ▼ core/sentiment.py      จำแนกอารมณ์ระดับรีวิว + ระดับอนุประโยค (WangchanBERTa หรือ lexicon)
   ▼ core/aspect.py         จัดหมวดระดับอนุประโยค (food/service/ambience)
   ▼ core/phrases/*         สกัดวลีความเห็น 7 ขั้น (rule) หรือ core/phrases/llm_extract.py (Gemini)
   ▼ core/insights.py       สร้างข้อเสนอแนะเชิงปฏิบัติราย aspect
   ▼ core/pipeline.py       ประกอบเป็น dict 11 คีย์
   ▼ db/database.py         เก็บลง SQLite (payload = JSON)
   ▼ templates/dashboard    แสดงผล: การ์ดอารมณ์ + donut + ตาราง + วลีแยกหมวด + insight
```

**dict ผลลัพธ์ (11 คีย์) จาก `run_analysis()`:**
`store_name`, `source_url`, `total_reviews` (ไทยหลังคัด), `fetched_reviews` (ดึงมาทั้งหมด),
`engine` (เครื่องมือ sentiment ที่ใช้จริง), `extract_engine` (rule/llm ที่ทำงานจริง),
`distribution` (counts+pct), `aspect_summary`, `keywords` (วลีราย aspect/อารมณ์), `insights`, `reviews`

**เครื่องยนต์คู่ + fallback อัตโนมัติ (จุดเด่นทางวิศวกรรม):**
- Sentiment: WangchanBERTa → ถ้าโหลดไม่สำเร็จ → lexicon (และ `engine_name()` รายงานตามจริง)
- Phrase: Gemini (ถ้าเลือก+มี key) → ถ้า error/โควตาหมด → rule-based (และรายงาน `extract_engine` ตามจริง)

---

## 3. วิธีการเชิงเทคนิคแบบละเอียด (สำหรับเขียนบทที่ 3)

### 3.1 การเตรียมข้อความ (Preprocessing) — `core/preprocess.py`
1. **คัดภาษาไทย** `is_thai(text, threshold=0.2)`: นับสัดส่วนอักษรไทย (`฀–๿`) ต่ออักขระที่ไม่ใช่ช่องว่าง ≥ 0.2 → ไทย
2. **ทำความสะอาด** `clean_text()`: ลบ URL, อีโมจิ (ช่วง Unicode emoji), อักขระพิเศษ (คงไทย/อังกฤษ/ตัวเลข/ช่องว่าง),
   ลดคำยืดเสียง (ตัวซ้ำ ≥ 3 → 1 เช่น `อร่อยยยย→อร่อย`), แปลงอังกฤษเป็นพิมพ์เล็ก, `pythainlp.util.normalize`
3. **ตัดคำ** `tokenize()`: PyThaiNLP engine `newmm` (มี fallback ตัดด้วยช่องว่างถ้าไม่มีไลบรารี)
4. **แบ่งอนุประโยค** `clause.split_clause_tokens()`: แยกที่ marker token `{แต่, แต่ว่า, อย่างไรก็ตาม}` —
   **ทำที่ระดับ token** (กันบั๊ก substring เช่นคำว่า `ตกแต่ง` ที่มี "แต่" อยู่ข้างใน)
5. **คำปฏิเสธ** `negation.apply_negation()`: รวม negator + คำขั้วถัดไปทันที → token เดียว (`ไม่`+`อร่อย`→`ไม่อร่อย`)
   *ก่อน* ลบ stopword (ไม่งั้น "ไม่" โดนทิ้งแล้วความหมายพลิก)
6. **ลบคำหยุด** `remove_stopwords()`: ใช้ stopwords ของ PyThaiNLP

**3 token views ต่ออนุประโยค** (สำคัญ — อธิบายให้กรรมการได้):
| view | ผ่าน negation? | ผ่าน stopword removal? | ใช้ที่ |
|---|---|---|---|
| `raw_tokens` | ❌ | ❌ | **การสกัดวลี** (ต้องการคำครบ) |
| `tokens` | ✅ รวม | ✅ | lexicon sentiment (backstop) |
| `tokens_base` | ❌ | ✅ | **การจัดหมวด aspect** |

### 3.2 การจำแนกอารมณ์ (Sentiment) — `core/sentiment.py`
- **WangchanBERTa (โหมดวิจัย):** `airesearch/wangchanberta-base-att-spm-uncased`
  revision **`finetuned@wisesight_sentiment`** ผ่าน `transformers.pipeline("sentiment-analysis")`
  - โมเดลคืน **4 คลาส** (pos/neu/neg/**question**) → โค้ดแมป `question → neutral` เหลือ 3 คลาส (`_WISESIGHT_MAP`)
  - ตัดข้อความที่ 512 token, โหลดแบบ lazy singleton (โหลดครั้งเดียว)
  - **⚠️ ความจริงที่ต้องเขียนให้ถูก:** เป็น checkpoint ที่ fine-tune มาแล้วบนคลัง **Wisesight (โซเชียลมีเดีย)**
    นำมาใช้แบบ off-the-shelf/transfer **ไม่ได้ fine-tune เพิ่มด้วยรีวิวร้านอาหารเอง** (ในโค้ดไม่มี training script)
- **Lexicon (baseline/fallback):** `_predict_lexicon()` นับ `word_polarity` ของแต่ละ token (เข้าใจ negation)
  ถ้าไม่เจอคำขั้วเลย ลอง substring กับข้อความรวม → ตัดสินจากจำนวนคำบวก vs ลบ
- **`classify_phrase()` (ขั้น 6 ของการสกัดวลี):** (1) ถ้าวลีมีขั้วของตัวเอง ใช้ขั้วนั้น (`ราคาแพง`=ลบ แม้ในประโยคบวก)
  (2) ถ้ากำกวม (เช่น `คนเยอะ`) → ใช้อารมณ์ของอนุประโยคต้นทาง (reuse cache ไม่เรียกโมเดลซ้ำ)

### 3.3 การสกัดวลีความเห็น 7 ขั้น (Rule-based) — `core/phrases/`
| ขั้น | ไฟล์ | สิ่งที่ทำ |
|---|---|---|
| 1 Extract | `extract.py` | จับ idiom/MWE (longest-match) → ไวยากรณ์เชิงพจนานุกรม รูปแบบ P1–P7 + overlap suppression |
| 2 Quality | `quality.py` | กรองวลีขยะ: ทิ้ง META_VERBS (`ชอบ`,`แนะนำ`), ทิ้งคำนามเดี่ยว, ทิ้ง bare descriptor conf ต่ำ (กัน hallucination) |
| 3 Canonical | `canonical.py` | สร้าง `canonical`/`agg_key` (ตัด intensifier เพื่อนับ) + `display` (เก็บคำเดิม); gated head-noun synthesis |
| 4 Synonyms | `synonyms.py` | รวมคำพ้องผ่าน whitelist `MEMBER_TO_CONCEPT` เท่านั้น (อนุรักษ์นิยม) |
| 5 Aspect | `aspect.py` `route_aspect()` | จัดหมวด 4 ชั้น (ดู 3.4) |
| 6 Sentiment | `sentiment.py` `classify_phrase()` | ตีอารมณ์รายวลี (ดู 3.2) |
| 7 Aggregate | `aggregate.py` | นับ + จัดอันดับ → `{aspect:{positive/neutral/negative:[{word,count}]}}` (TOP_N=6) |

**รูปแบบไวยากรณ์ (patterns) ใน extract.py — เขียนเป็นตารางในบทที่ 3 ได้:**
| รูปแบบ | คำอธิบาย | ตัวอย่าง |
|---|---|---|
| idiom | วลีตายตัวจาก `IDIOMS` | (4 รายการในพจนานุกรม) |
| P1 | NOUN + descriptor | `อาหาร`+`อร่อย` → `อาหารอร่อย` |
| P2 | NOUN + NEG + descriptor | `อาหาร`+`ไม่`+`อร่อย` → `อาหารไม่อร่อย` |
| P3/B1 | กู้คำประสมจาก lexicon | `รอ`+`นาน` → `รอนาน` |
| P7 | descriptor ไร้คำนาม / คำประสม / negator+desc | `ติดริมน้ำ`, `เย็นสบาย`, `ไม่ประทับใจ` |

**ทำไมไม่ใช้ POS tagging:** ทีมประเมิน POS ของ PyThaiNLP แล้วพบติดป้ายคำแสดงความเห็นไทยผิดบ่อย
(`อร่อย`→NOUN, `ดี`→ADV) จึงเลือกไวยากรณ์เชิงพจนานุกรมที่ **คงเส้นคงวาและอธิบายได้** (docstring `extract.py`)

### 3.4 การจัดหมวด 4 ชั้น (Aspect routing) — `aspect.py route_aspect()`
เรียงจาก **แม่นไปหลวม** (คืน aspect + ระดับความเชื่อมั่น):
1. **idiom/concept** — mapping ที่ดูแลเอง (`IDIOMS`, `SYNONYM_GROUPS`) → conf `high`
2. **คำนามหัวหมวด** — `head_noun ∈ NOUN_TO_ASPECT` → `high`
3. **บริบทอนุประโยค** — ถ้าอนุประโยคพูดถึงหมวดเดียวชัดเจน → `high`
4. **คำขยายบ่งหมวด** — `descriptor ∈ DESCRIPTOR_ASPECT_HINTS` → `medium`
- 3 หมวด: **อาหาร (รวมราคา) / บริการ / บรรยากาศ** (internal `food/service/atmosphere` → dashboard `ambience`)

### 3.5 ข้อเสนอแนะเชิงปฏิบัติ — `core/insights.py`
กฎ (threshold ปรับได้): ต่ออนุประโยคราย aspect
- ต้องมี ≥ **5** รีวิว (`MIN_SAMPLE`) ถึงจะสรุป ไม่งั้นแจ้ง "ข้อมูลน้อย"
- negative ratio ≥ **0.30** (`WEAK_THRESHOLD`) → "ควรปรับปรุง" (แนบคำเชิงลบที่พบบ่อย)
- positive ratio ≥ **0.65** (`STRONG_THRESHOLD`) → "จุดแข็ง"
- อื่น ๆ → "ปานกลาง"
- เรียง "ควรปรับปรุง" ขึ้นก่อน เพื่อให้เจ้าของร้านเห็นสิ่งที่ต้องแก้ทันที
> **ที่มาของเลข threshold:** เป็นค่าที่ตั้งจากการพิจารณาเชิงปฏิบัติ (heuristic) ไม่ได้มาจากการ tune เชิงสถิติ —
> ถ้ากรรมการถาม ให้ตอบตรง ๆ ว่าเป็น design choice ที่ปรับได้ และเสนอเป็นงานต่อยอด (tune จากข้อมูลจริง)

### 3.6 เครื่องยนต์ Gemini (LLM) — `core/phrases/llm_extract.py`
- ส่งรีวิวทั้งชุดเป็น **request เดียว** ให้ Gemini พร้อม `response_schema` บังคับคืน `{phrase, aspect, sentiment}`
- โมเดลเริ่มต้น `gemini-2.5-flash-lite` (free tier ใช้ได้จริง), เปลี่ยนเป็น `gemini-2.5-flash` ได้ถ้ามีโควตา
- กรองวลียาว > 40 อักขระทิ้ง (กัน "ทั้งประโยค" หลุดมา)
- `available()` เช็คทั้ง API key และ import SDK; ถ้าไม่พร้อม/error → fallback rule-based
- **ข้อพิจารณาเชิงจริยธรรม/วิจัย:** โหมดนี้ส่งข้อความรีวิวออกไปยัง Google (privacy), มีโควตา/ค่าใช้จ่าย,
  ผลไม่ deterministic — จึงเป็น opt-in และมี rule-based เป็นค่าเริ่มต้นที่ทำงานออฟไลน์

---

## 4. ชุดข้อมูล: ที่มา โครงสร้าง การขยาย

| ไฟล์ | จำนวน | โครงสร้าง | ใช้ทำอะไร |
|---|---|---|---|
| `data/sample_reviews.json` | 30 รีวิว (ร้าน "ครัวบ้านสวน") | `{text, rating, review_date}` | โหมด demo (แทน Apify) |
| `data/labeled_reviews.json` | 60 รีวิว (balance 20/20/20) | `{text, label}` (label∈ positive/neutral/negative) | **ชุดทดสอบ gold สำหรับบทที่ 4** |
| `data/settings.json` | — | `{max_reviews, use_model, extract_engine}` | ค่าตั้งฝั่งผู้ใช้ |

**⚠️ สิ่งที่ต้องเขียน/เตรียมตอบเรื่องชุดข้อมูล (กรรมการถามแน่):**
- ระบุ **ที่มาของ 60 รีวิว** (ดึงจากร้านจริงหรือสร้างเอง?), **ใครติด label**, มีการวัด inter-annotator agreement ไหม
- ชุด balance 20/20/20 ทำให้ Macro-F1 = Weighted-F1 และตัวเลขอาจ "ดูดีเกินจริง" เทียบรีวิวจริงที่ไม่ balance
- 60 รายการถือว่าเล็ก → ระบุเป็นข้อจำกัด + เสนอขยายเป็น ~400 ด้วย `label_tool.py`

**วิธีขยายชุดทดสอบ (workflow ครบวงจร):**
```bash
# 1) วิเคราะห์ร้านจริง → หน้า dashboard → ปุ่ม Export "รีวิวสำหรับติด label (JSON)"
#    (หรือ GET /export/<aid>/labeling.json)
# 2) ติด label ทีละรีวิว (กด p=บวก / u=กลาง / n=ลบ / s=ข้าม / q=บันทึกออก)
python eval/label_tool.py for_labeling_<aid>.json
# 3) วัดผลใหม่
python eval/evaluate.py
```

---

## 5. การทดลองและการประเมินผล (สำหรับบทที่ 4)

### 5.1 คำสั่งสร้างผลทุกตัว (reproducible)
```bash
# ประเมินอารมณ์ด้วย lexicon (โหมด demo)
python eval/evaluate.py
# ประเมินอารมณ์ด้วย WangchanBERTa จริง (ต้อง pip install -r requirements-model.txt)
USE_MODEL=1 python eval/evaluate.py
# เปรียบเทียบเครื่องยนต์สกัดวลี rule vs Gemini
python -m scripts.compare_engines          # rule อย่างเดียว
python -m scripts.compare_engines --llm     # + Gemini (ต้องมี GEMINI_API_KEY)
# รันชุดทดสอบทั้งหมด (พิสูจน์ระบบทำงาน)
python -m unittest discover -s tests        # → Ran 135 tests ... OK
```
ผลถูกเขียนอัตโนมัติที่ `eval/report.txt`, `eval/confusion_matrix.csv` (+`.png` ถ้ามี matplotlib)

### 5.2 ตัวชี้วัดที่คำนวณ (ทั้งหมดเขียนเอง ไม่พึ่ง scikit-learn) — `eval/evaluate.py`
| ตัวชี้วัด | สูตร | ความหมาย |
|---|---|---|
| Accuracy | (ทำนายถูก)/(ทั้งหมด) | ความถูกต้องรวม |
| Precision (รายคลาส) | TP/(TP+FP) | ทำนายว่าคลาสนี้แล้วถูกแค่ไหน |
| Recall (รายคลาส) | TP/(TP+FN) | จับคลาสนี้ได้ครบแค่ไหน |
| F1 | 2·P·R/(P+R) | ค่าเฉลี่ยฮาร์มอนิก P,R |
| Macro-F1 | เฉลี่ย F1 ทุกคลาสเท่ากัน | ไม่ลำเอียงตามความถี่ |
| Weighted-F1 | เฉลี่ย F1 ถ่วงด้วย support | สะท้อนการกระจายจริง |
| Cohen's Kappa | (pₒ−pₑ)/(1−pₑ) | ความสอดคล้องเหนือความบังเอิญ |

**เกณฑ์ตีความ Kappa:** <0.20 น้อย, 0.21–0.40 พอใช้, 0.41–0.60 ปานกลาง, 0.61–0.80 สูง, 0.81–1.00 เกือบสมบูรณ์
→ ของเรา **0.825 = เกือบสมบูรณ์**

### 5.3 สิ่งที่บทที่ 4 ควรมี (โครงเนื้อหา)
1. ผลการพัฒนาระบบ (ฟังก์ชันครบ + 135 เทสต์ผ่าน) + **screenshot แดชบอร์ดจริง** (ต้องแคปเอง)
2. ตัวอย่างผลการสกัดวลี (เช่น "อาหารอร่อยมาก แต่บริการช้า" → แยกหมวดถูก)
3. ตารางผลประเมินอารมณ์ (ภาพรวม + รายคลาส + confusion matrix) ← มีใน `report.txt`
4. **Error Analysis** (โดยเฉพาะ neutral recall 0.70) — วิเคราะห์ว่าทำไมพลาด
5. การเปรียบเทียบ rule vs Gemini (เชิงคุณภาพ จาก `compare_engines.py`)
6. อภิปรายผลเทียบงานวิจัยที่เกี่ยวข้อง (บทที่ 2)

---

## 6. วิธีรันระบบครบทุกโหมด

### 6.1 ติดตั้ง
```bash
pip install -r requirements.txt           # โหมด demo (เบา: Flask, requests, pythainlp, google-genai)
pip install -r requirements-model.txt     # + WangchanBERTa (transformers, torch ~2GB)
python app.py                             # เปิด http://127.0.0.1:5000
```

### 6.2 ตัวแปร config (`.env`, คัดลอกจาก `.env.example`)
| ตัวแปร | ค่าเริ่มต้น | ความหมาย | ใครตั้ง |
|---|---|---|---|
| `APIFY_TOKEN` | (ว่าง→demo) | กุญแจดึงรีวิวจริง | ผู้ดูแลระบบ |
| `MAX_REVIEWS` | 100 | เพดานจำนวนรีวิว/ร้าน | ผู้ดูแลระบบ |
| `USE_MODEL` | 0 | 1 = ใช้ WangchanBERTa | (ผู้ใช้ปรับผ่าน Settings ได้) |
| `MODEL_NAME` | `airesearch/wangchanberta-base-att-spm-uncased` | checkpoint | — |
| `MODEL_REVISION` | `finetuned@wisesight_sentiment` | revision 4 คลาส | — |
| `GEMINI_API_KEY` | (ว่าง→ปิด LLM) | เปิดเครื่องยนต์ Gemini | ผู้ดูแลระบบ |
| `GEMINI_MODEL` | `gemini-2.5-flash-lite` | โมเดล Gemini | — |
| `FLASK_DEBUG` | 0 | 1 = เปิด debugger (อันตราย) | dev เท่านั้น |

> **สำคัญสำหรับการสาธิต/ทำผลวิจัย:** ค่าใน `data/settings.json` (ฝั่งผู้ใช้) **ทับ** ค่า env บางตัว
> (`use_model`, `extract_engine`, `max_reviews`) — ก่อนเก็บผลให้เช็กว่าตั้งโหมดที่ต้องการรายงาน
> ปัจจุบันเครื่องนี้ตั้ง `use_model:true` → รัน WangchanBERTa จริง

### 6.3 หน้าเว็บ & API
| Route | หน้าที่ |
|---|---|
| `GET /` | หน้าแรก (กรอก URL) |
| `POST /analyze` | รัน pipeline → เก็บ DB → ไป dashboard |
| `GET /dashboard/<id>` | แดชบอร์ดผลวิเคราะห์ |
| `GET /history` `/saved` | ประวัติ / รายการโปรด |
| `POST /toggle-save/<id>` `/delete/<id>` | สลับโปรด / ลบ (JSON) |
| `GET /api/analysis/<id>` | ผลเต็มเป็น JSON |
| `GET/POST /settings` | ตั้งค่าเครื่องมือ + จำนวนรีวิว |
| `GET /export/<id>/{reviews,summary}.csv`, `/labeling.json` | ส่งออกข้อมูล |

---

## 7. การขยายพจนานุกรม (lexicon)

**ทุกอย่างอยู่ที่ `core/lexicon.py` (จุดเดียว = single source of truth)** — เพิ่มคำที่นี่ที่เดียวมีผลทั้งระบบ

| โครงสร้าง | จำนวนปัจจุบัน | หน้าที่ | เพิ่มเมื่อ |
|---|---|---|---|
| `ASPECT_LEXICON` | 3 หมวด | คำบ่งหมวด food/service/ambience | เพิ่มคำบ่งหมวด |
| `SENTIMENT_WORDS` | บวก 32 / ลบ 29 | คำขั้วอารมณ์ (lexicon sentiment + negation) | เจอคำบวก/ลบใหม่ |
| `ASPECT_NOUNS` → `NOUN_TO_ASPECT` | 44 | คำนามหัวหมวด | เจอคำนามหมวดใหม่ |
| `DESCRIPTOR_ASPECT_HINTS` | 41 | คำขยายที่บ่งหมวดได้ | เจอคำขยายบ่งหมวด |
| `IDIOMS` | 4 | วลีตายตัว + หมวด/canonical | เจอสำนวน |
| `SYNONYM_GROUPS` → `MEMBER_TO_CONCEPT` | 4 / 15 | รวมคำพ้องความหมายเดียว | เจอคำพ้อง |
| `INTENSIFIERS` | `มาก, สุดๆ, จริงๆ,...` | คำเน้น (ตัดตอนนับ) | — |
| `FILLERS` | `คือ, ที่, อะ, นะ, ก็` | คำเติม (ตัดทิ้ง) | — |
| `META_VERBS` | `ชอบ, แนะนำ, บอก, คิดว่า, รู้สึก` | คำอภิปราย (ไม่ใช่วลีความเห็น) | — |
| `NO_SYNTH_DESCRIPTORS` | `คึกคัก` | คำที่สมบูรณ์ในตัว ไม่ต้องเติมคำนาม | — |

> **ข้อจำกัดที่ต้องระบุในเล่ม:** คำที่ไม่อยู่ใน lexicon (สแลงใหม่) จะไม่ถูกจับ — ระบบไม่เรียนรู้คำเอง
> วิธีปรับปรุงคือเพิ่มคำด้วยมือ (นี่คือเหตุผลที่ Gemini engine มีประโยชน์ในรีวิวภาษาธรรมชาติหลากหลาย)

---

## 8. ผลปัจจุบันและการตีความ

**ผลประเมินอารมณ์ (WangchanBERTa, n=60) — จาก `eval/report.txt`:**
- Accuracy **0.8833**, Macro-F1 **0.8792**, Weighted-F1 **0.8792**, Kappa **0.8250**

| คลาส | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| positive (บวก) | 0.826 | 0.950 | 0.884 | 20 |
| neutral (กลาง) | 1.000 | 0.700 | 0.824 | 20 |
| negative (ลบ) | 0.870 | 1.000 | 0.930 | 20 |

**Confusion Matrix** (แถว=จริง, คอลัมน์=ทำนาย): บวก[19,0,1] · กลาง[4,14,2] · ลบ[0,0,20]

**การตีความ (เขียนในบทที่ 4 ได้):**
- เชิงลบจับได้สมบูรณ์ (recall 1.00), เชิงบวกพลาด 1
- **จุดอ่อน = neutral (recall 0.70)** ถูกทำนายเป็นบวก 4 / ลบ 2 — รีวิวกลางหลายอันมีถ้อยคำประเมินปน
  ทำให้โมเดลเอนไปขั้วใดขั้วหนึ่ง แต่ **Precision ของ neutral = 1.00** (ทำนายว่ากลางเมื่อไรถูกเสมอ)
- **ตัวอย่างผลสกัดวลีจริง (รัน demo):** จาก 30 รีวิว → 35 วลี ครบ 3 หมวด เช่น `อาหารอร่อย`(×4),
  `วัตถุดิบสด`(×2); negation ถูก: `ไม่ค่อยประทับใจ`, `วัตถุดิบไม่สด` → negative

---

## 9. ข้อจำกัดและสิ่งที่ต้องระวังในห้องสอบ

| # | ข้อจำกัด/ความเสี่ยง | ระดับ | สิ่งที่ต้องทำ |
|---|---|---|---|
| 1 | **ไม่ได้ fine-tune** WangchanBERTa เอง (ใช้ Wisesight off-the-shelf) | 🔴 สูง | เขียนให้ตรง — อย่าเคลมว่า fine-tune; หรือไป fine-tune จริงบน Colab |
| 2 | **ค่าเริ่มต้นโค้ดคือ lexicon + rule** (แต่เครื่องนี้ตั้ง use_model:true) | 🟠 | ระบุชัดว่ารายงานผลจากโหมดไหน; lexicon=baseline, WangchanBERTa=วิจัย |
| 3 | การสกัดวลี **ไม่มี gold set ราย phrase** วัดเชิงปริมาณ | 🟠 | ระบุเป็นข้อจำกัด + เสนองานต่อยอด; ใช้ตัวอย่างเชิงคุณภาพแทน |
| 4 | ชุดทดสอบ **60 รายการ balance เทียม** | 🟠 | ระบุ + เสนอขยาย + อภิปรายว่าผลจริงอาจต่าง |
| 5 | Gemini ส่งข้อมูลออกภายนอก + มีค่าใช้จ่าย/โควตา | 🟡 | ระบุ privacy/cost + ว่ามี fallback + เป็น opt-in |
| 6 | negation มองแค่คำขั้วติดกัน 1 คำ; clause split เฉพาะกลุ่ม "แต่" | 🟡 | ระบุเป็น scope/limitation |
| 7 | ไม่มี auth/CSRF; synchronous ไม่ scale | 🟡 | ระบุว่าออกแบบให้รันเฉพาะที่ ไม่ใช่ public |
| 8 | spec รอบแรกพูดถึง Claude/POS ที่เลิกใช้ | 🟡 | ใส่หมายเหตุ superseded หรือไม่อ้างถึงในเล่ม |

---

## 10. เช็กลิสต์สิ่งที่ต้องทำก่อนส่งเล่ม

**🔴 ต้องทำ (Critical):**
- [ ] ตัดสินใจเรื่อง fine-tuning: ทำจริง (Colab) **หรือ** แก้ถ้อยคำในเล่มให้เป็น "ใช้ pre-finetuned/transfer"
- [ ] เติม **บทที่ 4** จาก `eval/report.txt` + screenshot dashboard จริง + ระบุโหมดที่รายงาน
- [ ] เขียน **บทที่ 3** ให้ครบ methodology จริง (phrase 7 ขั้น, negation, clause, aspect 4-tier, insights, Gemini)
- [ ] เติม **บทที่ 5** (สรุป/ข้อจำกัด/ข้อเสนอแนะ — ดึงจากหัวข้อ 9 ของคู่มือนี้ได้)
- [ ] เพิ่มหัวข้อ **Gemini engine** + เปรียบเทียบ rule vs LLM

**🟠 ควรทำ (Important):**
- [ ] อธิบายที่มา/วิธี label ของ 60 รีวิว + พยายามขยายชุด
- [ ] เพิ่ม Error Analysis (neutral) + อภิปราย balance เทียม
- [ ] แก้ขอบเขตในเล่ม: SQLite (ไม่ใช่ CSV ล้วน), เพิ่ม JavaScript, ระบุ 2 เครื่องยนต์

**🟡 ขัดเกลา (Optional):**
- [ ] แก้คำสะกด: Takenization→Tokenization, Unstructure→Unstructured, Pre-trainnng→Pre-training, Lowik→Lowphansirikul
- [ ] แก้ field "Error! Reference source not found." (รูป/ตารางอ้างอิง)
- [ ] เพิ่ม diagram สถาปัตยกรรม/sequence ของ pipeline จริง + รายงาน latency

**ร่างที่ทำให้แล้ว (ใช้เป็นฐานได้):** `output/InsightReview-Thesis-v100.pdf` ครอบ Critical ส่วนใหญ่แล้ว
(เหลือแค่ screenshot จริง + decision เรื่อง fine-tune + ปรับสำนวนเอง)

---

## 11. คลังคำถามกรรมการ + คำตอบตัวอย่าง

### กลุ่มโมเดล
**Q1: fine-tune WangchanBERTa เองไหม?**
> ไม่ได้ fine-tune เพิ่ม ใช้ checkpoint `finetuned@wisesight_sentiment` ที่ทีม VISTEC fine-tune มาแล้วบนคลัง Wisesight
> แบบ transfer/off-the-shelf เนื่องจากข้อจำกัดด้านข้อมูล label และทรัพยากร เราประเมินความสามารถบนโดเมนรีวิวร้านอาหาร
> โดยตรง (ได้ Acc 88.3%) และเสนอ fine-tune เฉพาะโดเมนเป็นงานต่อยอด

**Q2: ทำไม checkpoint โซเชียลมีเดียถึงใช้กับรีวิวร้านอาหารได้?**
> Wisesight เป็นข้อความความเห็นภาษาไทยทั่วไปที่มีลักษณะใกล้รีวิว (ไม่เป็นทางการ มีอารมณ์) ผลทดสอบบนรีวิวร้านอาหาร
> จริงยืนยันว่าถ่ายโอนได้ดี (Kappa 0.825) จุดอ่อนเดียวคือคลาส neutral ซึ่งเป็นข้อจำกัดที่เราระบุไว้

**Q3: ตัวเลขในเล่มมาจากโหมดไหน (lexicon หรือ WangchanBERTa)?**
> มาจาก WangchanBERTa (`USE_MODEL=1`) — โหมด lexicon เป็น baseline ที่ทำให้ระบบรันได้ทันทีโดยไม่ต้องโหลดโมเดล

**Q4: neutral recall แค่ 0.70 เพราะอะไร?**
> รีวิวกลางหลายรายการมีถ้อยคำเชิงประเมินปนอยู่ (ชม+ติในประโยคเดียว) โมเดลจึงเอนไปขั้วใดขั้วหนึ่ง
> แต่ Precision ของ neutral = 1.00 หมายความว่าเมื่อทำนายว่ากลางจะถูกเสมอ การแก้คือเพิ่มตัวอย่างกลางที่หลากหลาย

### กลุ่มชุดข้อมูล
**Q5: 60 รีวิว label จากไหน ใคร label?** → *(ต้องเตรียมคำตอบจริง: ดึงจากร้านใด, ผู้วิจัย 2 คนติด label, เกณฑ์อย่างไร)*
**Q6: ทำไม balance 20/20/20?** → เพื่อให้ตัวชี้วัดรายคลาสไม่ลำเอียงจากความถี่; ยอมรับว่าไม่สะท้อนการกระจายจริง จึงระบุเป็นข้อจำกัด
**Q7: 60 พอไหม?** → เป็นชุดเริ่มต้น มีเครื่องมือ `label_tool.py` ขยายได้ถึง ~400; ระบุเป็น future work

### กลุ่ม phrase extraction / Gemini
**Q8: "Keyword Extraction" ในเล่มคือ phrase extraction ใช่ไหม?**
> ใช่ — จริง ๆ เราสกัด "วลี" (เช่น `ราคาไม่แพง`) ไม่ใช่คำเดี่ยว ผ่าน pipeline 7 ขั้นเชิงพจนานุกรม เป็น contribution หลัก
> (ฉบับเล่มที่ปรับปรุงแล้วเขียนส่วนนี้ครบในบทที่ 3)

**Q9: ทำไมไม่ใช้ POS tagging?** → ประเมิน POS ของ PyThaiNLP แล้วติดป้ายคำความเห็นไทยผิดบ่อย (`อร่อย`→NOUN) เลือกไวยากรณ์พจนานุกรมที่อธิบายได้แทน
**Q10: Gemini อยู่ตรงไหน privacy เป็นยังไง?** → เครื่องยนต์ทางเลือกในขั้นสกัดวลี ส่งรีวิวให้ Google (opt-in), มี fallback rule-based ที่ทำงานออฟไลน์เป็นค่าเริ่มต้น
**Q11: วัดคุณภาพ phrase ยังไง?** → ปัจจุบันเชิงคุณภาพ (ยังไม่มี gold ราย phrase) — ระบุเป็นข้อจำกัด + future work

### กลุ่มระบบ
**Q12: clause split ทำไมแค่ "แต่"?** → อนุรักษ์นิยมเพื่อกันแบ่งผิด; "และ/ส่วน" กำกวมเกินไป — เป็น scope
**Q13: negation ครอบคลุมแค่ไหน?** → คำขั้วติดกัน 1 คำ; เคสซับซ้อน ("ไม่อร่อยเท่าไหร่") เป็นข้อจำกัด
**Q14: threshold insights มาจากไหน?** → design choice เชิงปฏิบัติ ปรับได้; เสนอ tune จากข้อมูลจริงเป็นงานต่อยอด
**Q15: เก็บ CSV หรือ SQLite?** → SQLite (เล่มฉบับปรับปรุงแก้ขอบเขตแล้ว) + รองรับ export CSV/JSON
**Q16: รองรับผู้ใช้พร้อมกันกี่คน?** → ออกแบบ single-user/รันเฉพาะที่ (synchronous); public ต้องเพิ่ม queue+auth — ระบุไว้

---

## 12. ตารางอ้างอิงคำกล่าวอ้าง → ไฟล์โค้ด (Claim ↔ Evidence)

> ใช้ตอนเขียนเล่ม: ทุกประโยคที่เคลมในเล่มควรชี้ไฟล์ได้ เพื่อกันกรรมการจับว่า "เขียนแต่ไม่มีในโค้ด"

| คำกล่าวอ้างในเล่ม | ไฟล์ที่พิสูจน์ |
|---|---|
| ดึงรีวิวผ่าน Apify | `core/scraper.py` (`compass~google-maps-reviews-scraper`) |
| คัดเฉพาะภาษาไทย | `core/preprocess.py` `is_thai()` |
| ทำความสะอาด + normalize ยืดเสียง | `core/preprocess.py` `clean_text()`, `_REPEAT_RE` |
| ตัดคำ newmm + stopwords | `core/preprocess.py` `tokenize()`, `remove_stopwords()` |
| แบ่งอนุประโยค | `core/clause.py` `split_clause_tokens()` |
| จัดการคำปฏิเสธ | `core/negation.py` `apply_negation()`, `word_polarity()` |
| WangchanBERTa จำแนกอารมณ์ | `core/sentiment.py` `_load_model()`, `_predict_model()` |
| แมป question→neutral | `core/sentiment.py` `_WISESIGHT_MAP` |
| สกัดวลี 7 ขั้น | `core/phrases/{extract,quality,canonical,synonyms,aggregate}.py` + `aspect.py` + `sentiment.py` |
| จัดหมวด 4 ชั้น | `core/aspect.py` `route_aspect()` |
| ข้อเสนอแนะเชิงปฏิบัติ | `core/insights.py` `generate_insights()` |
| เครื่องยนต์ Gemini + fallback | `core/phrases/llm_extract.py`, `core/pipeline.py` `_phrase_pipeline()` |
| % รวมเป็น 100 เสมอ | `core/pipeline.py` `_percentages()` (largest-remainder) |
| เก็บ SQLite + history/save | `db/database.py` |
| export CSV/JSON | `core/export.py` |
| ประเมิน F1/Kappa | `eval/evaluate.py`, ผลใน `eval/report.txt` |
| 135 เทสต์ผ่าน | `tests/` (`python -m unittest discover -s tests`) |

---

## 13. แผนการดำเนินงาน (Gantt) และการ map กับบทในเล่ม

| กิจกรรม (ตาราง 1.1 ในเล่ม) | ช่วงเวลา 2569 | ผลผลิต/บทที่เกี่ยวข้อง |
|---|---|---|
| ศึกษา/รวบรวมข้อมูลที่เกี่ยวข้อง | มี.ค.–เม.ย. | บทที่ 2 |
| ศึกษาการดึงรีวิวจาก Google Maps | เม.ย.–พ.ค. | บทที่ 2/3 (Apify) |
| พัฒนา/กรองข้อมูลรีวิว | พ.ค.–มิ.ย. | บทที่ 3 (preprocess) |
| พัฒนาโมเดลวิเคราะห์อารมณ์ | มิ.ย.–ก.ค. | บทที่ 3 (sentiment) |
| พัฒนาเว็บแอป | ก.ค.–ส.ค. | บทที่ 3 (UI/Flask) |
| ทดสอบ + ประเมินผลผู้ใช้จริง | ส.ค.–ก.ย. | บทที่ 4 |
| สรุป + จัดทำรายงาน | ก.ย.–ต.ค. | บทที่ 4/5 |

> **หมายเหตุ:** กิจกรรม "ประเมินผลจากผู้ใช้จริง" (ส.ค.–ก.ย.) — ถ้ายังไม่ได้ทำ ควรวางแผนเก็บแบบประเมินความพึงพอใจ
> (เช่น แบบสอบถามเจ้าของร้าน/ผู้ใช้ทดลอง) เพื่อเติมบทที่ 4 ในมิติ usability นอกเหนือจาก F1

---

## 14. อภิธานศัพท์ (Glossary EN–TH)

| อังกฤษ | ไทย | นิยามสั้น |
|---|---|---|
| Sentiment Analysis | การวิเคราะห์ความคิดเห็น | จำแนกอารมณ์ข้อความ บวก/กลาง/ลบ |
| Opinion Phrase | วลีความเห็น | วลีสั้นที่นำไปตัดสินใจได้ เช่น "ราคาไม่แพง" |
| Aspect-Based Sentiment (ABSA) | การวิเคราะห์ความรู้สึกเชิงหมวด | ผูกอารมณ์เข้าหมวด อาหาร/บริการ/บรรยากาศ |
| Clause | อนุประโยค | ส่วนของประโยคที่แยกตามคำเชื่อมขัดแย้ง |
| Negation | การปฏิเสธ | คำที่พลิกความหมาย เช่น "ไม่อร่อย" |
| Tokenization | การตัดคำ | แยกข้อความเป็นหน่วยคำ |
| Lexicon | พจนานุกรม(คำ) | ฐานคำที่กำหนดเองสำหรับขั้ว/หมวด |
| Pre-trained Language Model | แบบจำลองภาษาฝึกล่วงหน้า | เช่น WangchanBERTa/BERT |
| Fine-tuning | การปรับจูนเฉพาะงาน | ฝึกโมเดลต่อด้วยข้อมูลงานเฉพาะ |
| Transfer Learning | การถ่ายโอนการเรียนรู้ | นำโมเดลที่ฝึกแล้วมาใช้กับงานใหม่ |
| Confusion Matrix | เมทริกซ์ความสับสน | ตารางจริง×ทำนาย |
| Macro-F1 | — | ค่าเฉลี่ย F1 ทุกคลาสเท่ากัน |
| Cohen's Kappa | — | ความสอดคล้องเหนือความบังเอิญ |
| LLM | แบบจำลองภาษาขนาดใหญ่ | เช่น Gemini |
| Dashboard | แดชบอร์ด | หน้าสรุปข้อมูลแบบรวมศูนย์ |

---

## 15. บรรณานุกรมและการอ้างอิง

**งานวิจัย/เอกสารหลัก (ใช้อ้างในเล่ม):**
- Lowphansirikul, L., et al. (2021). *WangchanBERTa: Pretraining transformer-based Thai language models.* arXiv:2101.09635
- Devlin, J., et al. (2019). *BERT: Pre-training of deep bidirectional transformers.* NAACL-HLT. arXiv:1810.04805
- Chevalier, J. A., & Mayzlin, D. (2006). *The effect of word of mouth on sales.* J. Marketing Research, 43(3).
- Liu, B. (2012). *Sentiment Analysis and Opinion Mining.* Morgan & Claypool.
- Jurafsky, D., & Martin, J. H. (2020). *Speech and Language Processing* (3rd ed.).
- Pontiki, M., et al. (2014). *SemEval-2014 Task 4: Aspect Based Sentiment Analysis.*
- ปราชญภาคย์ เหล่าสังข์สุข และคณะ (2560). *การวิเคราะห์ความคิดเห็นเกี่ยวกับร้านอาหารบนเว็บไซต์รีวิว.* วารสาร ม.ทักษิณ 20(1).
- กษิดิศ สุระรัตน์ชัย (2566). *Thai sentiment analysis with WangchanBERTa-CNN-BiLSTM.* จุฬาฯ
- Few, S. (2006). *Information Dashboard Design.* O'Reilly.
- Google. *Gemini API documentation.* https://ai.google.dev
- Apify. *Google Maps Reviews Scraper.* https://apify.com/compass/google-maps-reviews-scraper

**เอกสารภายในโปรเจกต์:**
- [README.md](../README.md) — ภาพรวม + วิธีรัน + methodology
- [docs/ANALYSIS.md](ANALYSIS.md) — วิเคราะห์ repo เชิงลึก (ไฟล์ต่อไฟล์)
- [docs/superpowers/specs/](superpowers/specs/) — เอกสารออกแบบ 3 ฉบับ (อ่านตามลำดับเวลา; รอบแรกยังพูดถึง Claude/POS ที่ภายหลังเลิกใช้)
- [docs/superpowers/plans/](superpowers/plans/) — แผนพัฒนา 3 ฉบับ
- `output/InsightReview-Thesis-v100.pdf` — ร่างเล่มฉบับสมบูรณ์
- `output/InsightReview-Review-Summary.pdf` — รายงานตรวจสอบความสอดคล้อง วิจัย↔โค้ด

---

> **คำแนะนำการใช้คู่มือนี้:** เริ่มจากหัวข้อ 10 (เช็กลิสต์) เพื่อรู้ว่าต้องทำอะไรบ้าง → หัวข้อ 3 เพื่อเขียนบทที่ 3 →
> หัวข้อ 5+8 เพื่อทำบทที่ 4 → หัวข้อ 11 เพื่อซ้อมสอบ → หัวข้อ 12 เพื่อตรวจว่าทุกคำกล่าวอ้างมีโค้ดรองรับ
