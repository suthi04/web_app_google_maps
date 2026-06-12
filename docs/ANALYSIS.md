# InsightReview — รายงานวิเคราะห์ Repository เชิงลึก

> จัดทำ: 2026-06-10 · branch `feat/review-insight-phrase-extraction`
> วิธีวิเคราะห์: อ่านทุกไฟล์ที่ track ใน git (79 ไฟล์), รัน test suite จริง, ตรวจ data/spec/plan,
> และตรวจสอบความถูกต้องของการเรียก Anthropic API เทียบเอกสารทางการ
> อ้างอิงจากโค้ดจริงทั้งหมด ไม่คาดเดา

---

## 1. Project Overview

**InsightReview** คือเว็บแอป (Flask) ที่วิเคราะห์รีวิวร้านอาหารจาก Google Maps แล้วสรุปเป็น
"ข้อมูลเชิงกลยุทธ์" ให้เจ้าของร้าน เป็น**โครงงานปริญญาตรี วท.บ. เทคโนโลยีสารสนเทศ
มหาวิทยาลัยนเรศวร** (ระบุใน [README.md:8](../README.md#L8))

**ปัญหาที่แก้:** ระบบวิเคราะห์รีวิวทั่วไปมักดึงแค่ "คำเดี่ยว" (`อาหาร`, `ดี`, `อร่อย`)
ซึ่งไม่บอกอะไรที่นำไปใช้ได้ โครงงานนี้ตั้งใจดึง **"วลีความเห็น" (opinion phrases)**
ที่นำไปตัดสินใจได้จริง เช่น `อาหารอร่อย`, `ราคาไม่แพง`, `รอนาน`, `ติดริมน้ำ`
พร้อมจำแนกหมวดและอารมณ์ของแต่ละวลี
(ดูเจตนาใน [docs/.../2026-06-09-review-insight-phrase-extraction-design.md:10-38](superpowers/specs/2026-06-09-review-insight-phrase-extraction-design.md#L10-L38))

**กลุ่มผู้ใช้:**
- **เจ้าของ/ผู้จัดการร้านอาหาร** — ดูแดชบอร์ดสรุปอารมณ์ + จุดแข็ง/ควรปรับปรุง
- **ผู้ทำวิจัย (ตัวนักศึกษา)** — ใช้ฟังก์ชัน export + eval วัด F1 สำหรับเขียนวิทยานิพนธ์บทที่ 4
- มีการแบ่ง "ผู้ดูแลระบบ" (ตั้ง `.env`) vs "ผู้ใช้ทั่วไป" (ตั้งผ่านหน้า Settings) อย่างชัดเจน
  ใน [config.py:84-93](../config.py#L84-L93)

**Workflow หลัก** (จาก [core/pipeline.py:71-115](../core/pipeline.py#L71-L115)):
```
URL → scraper (Apify/sample) → preprocess (คัดไทย+ตัดคำ+แบ่งอนุประโยค)
→ sentiment (WangchanBERTa/lexicon) → aspect (จัดหมวด)
→ phrase pipeline (สกัดวลี: rule หรือ Claude) → topics → insights
→ เก็บ SQLite → redirect ไป dashboard
```

จุดออกแบบสำคัญที่สุด: ระบบรันได้ทันทีใน **"โหมด demo"** โดยไม่ต้องมี Apify token
และไม่ต้องโหลดโมเดล (ใช้ [data/sample_reviews.json](../data/sample_reviews.json) 30 รีวิว + lexicon)

---

## 2. Architecture Analysis

| ชั้น | เทคโนโลยี | ไฟล์หลัก |
|---|---|---|
| **Frontend** | Jinja2 templates + Vanilla JS + CSS ล้วน (ไม่มี framework) | `templates/`, `static/` |
| **Backend** | Flask 3.1.3 (single process, monolithic) | [app.py](../app.py) |
| **Database** | SQLite (1 ตาราง `analysis`, เก็บผลเป็น JSON blob) | [db/database.py](../db/database.py) |
| **API** | REST-ish routes + JSON endpoints ภายใน | [app.py](../app.py) |
| **External** | Apify (`compass/google-maps-reviews-scraper`), Anthropic API | [core/scraper.py](../core/scraper.py), [core/phrases/llm_extract.py](../core/phrases/llm_extract.py) |
| **AI/ML** | WangchanBERTa (sentiment), Claude (phrase extraction), PyThaiNLP (tokenize) | [core/sentiment.py](../core/sentiment.py), [core/phrases/llm_extract.py](../core/phrases/llm_extract.py), [core/preprocess.py](../core/preprocess.py) |
| **3rd-party libs** | Flask, requests, pythainlp, anthropic; (optional) transformers, torch, sentencepiece, matplotlib | [requirements.txt](../requirements.txt), [requirements-model.txt](../requirements-model.txt) |

**หัวใจสถาปัตยกรรม:** pipeline แบบ **deterministic 7 ขั้นต่ออนุประโยค** ที่ทุกขั้นเป็น pure
function ทำงานบน `Phrase` dataclass หนึ่งตัว (อธิบายได้ทุกขั้น — สำคัญสำหรับการสอบป้องกัน
วิทยานิพนธ์) มี 2 "เครื่องยนต์" คู่ขนานที่ออกแบบให้ fallback อัตโนมัติ:
- **Sentiment:** WangchanBERTa → fallback lexicon
- **Phrase extraction:** LLM(Claude) → fallback rule-based

### Text Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          BROWSER (Jinja2 + vanilla JS)                    │
│   index · dashboard(donut CSS) · history · saved · settings · error       │
│   static/js: common.js (toast/modal/loading) · dashboard.js · history.js   │
└───────────────┬───────────────────────────────────────────────────────────┘
                │ HTTP (form POST / fetch JSON)
        ┌───────▼─────────────────────────────────────────────┐
        │                    app.py (Flask)                     │
        │  /  /analyze  /dashboard  /history  /saved            │
        │  /toggle-save  /delete  /api/analysis  /settings       │
        │  /export/*.csv|json   404/500 handlers                 │
        └───┬──────────────┬──────────────────┬─────────────────┘
            │              │                  │
   ┌────────▼───┐   ┌──────▼───────┐   ┌──────▼────────┐
   │ config.py  │   │ db/database  │   │ core/pipeline │  run_analysis(url)
   │ .env +     │   │ SQLite       │   └──────┬────────┘
   │ settings   │   │ analysis tbl │          │
   └────────────┘   └──────────────┘          │
                                              ▼
   scraper ─► preprocess ─► sentiment ─► aspect ─► PHRASE PIPELINE ─► keywords/topics ─► insights
   (Apify/   (clause+      (Wangchan/   (lexicon  ┌─ rule: extract→quality→canonical    │
    sample)   token views)  lexicon)     4-tier)  │   →synonyms→route→classify→aggregate │
                                                  └─ llm: llm_extract (Claude) ──────────┘
                                          │
       External: ── Apify API ──┐         │ ── Anthropic API (opt-in) ──┐
                  HuggingFace ───┘ (model) │                            │
                                  lexicon.py = single source of truth (nouns/descriptors/idioms/synonyms)
```

---

## 3. Repository Structure (ไฟล์ต่อไฟล์)

### Root
| ไฟล์ | หน้าที่ | เรียกจาก / ส่งต่อไป |
|---|---|---|
| [app.py](../app.py) | Flask routes ทั้งหมด, จุดเข้าระบบ | import `config`, `core.pipeline`, `core.export`, `db.database` |
| [config.py](../config.py) | ค่ากลางจาก `.env` + settings ฝั่งผู้ใช้ (`data/settings.json`) | ทุกโมดูลเรียกใช้ |
| [debug_apify.py](../debug_apify.py) | สคริปต์ตรวจการเชื่อมต่อ Apify 3 ขั้น (token → login → scrape) | สแตนด์อโลน, อ่าน `APIFY_TOKEN` |
| [requirements.txt](../requirements.txt) / [requirements-model.txt](../requirements-model.txt) | dependency demo / +model | — |
| [.env.example](../.env.example) | ตัวอย่าง config | — |

### core/ (ตรรกะวิเคราะห์)
| ไฟล์ | หน้าที่ | ความสัมพันธ์ |
|---|---|---|
| [core/pipeline.py](../core/pipeline.py) | ร้อยทุกขั้น → ผลลัพธ์ 1 dict | เรียกทุกโมดูลใน core; dispatch engine ([pipeline.py:44-52](../core/pipeline.py#L44-L52)) |
| [core/scraper.py](../core/scraper.py) | ดึงรีวิว Apify จริง / sample | เรียกจาก pipeline; ใช้ `config.get_apify_token()` เลือกโหมด |
| [core/preprocess.py](../core/preprocess.py) | คัดไทย+ทำความสะอาด+ตัดคำ+แบ่งอนุประโยค (3 token views) | ใช้ `clause`, `negation`; ผลิต `clauses` ที่ไหลต่อ |
| [core/clause.py](../core/clause.py) | แบ่งอนุประโยคตามคำเชื่อมขัดแย้ง (token-level) | เรียกจาก preprocess |
| [core/negation.py](../core/negation.py) | รวม "ไม่+คำขั้ว" + แหล่งความจริงเรื่องขั้วคำ (`word_polarity`) | นำเข้า `SENTIMENT_WORDS`; ใช้โดย preprocess/sentiment/extract |
| [core/lexicon.py](../core/lexicon.py) | **★ พจนานุกรมกลาง** (nouns/descriptors/idioms/synonyms) | source of truth ของ aspect, extract, sentiment, keywords |
| [core/sentiment.py](../core/sentiment.py) | จำแนกอารมณ์รีวิว/อนุประโยค + `classify_phrase` | ใช้ lexicon+negation; โหลดโมเดลแบบ lazy singleton |
| [core/aspect.py](../core/aspect.py) | จัดหมวดระดับอนุประโยค + `route_aspect` 4 ชั้น | ใช้ lexicon; เรียกจาก pipeline |
| [core/phrases/](../core/phrases/) | **★ การสกัดวลี (7 ขั้น)** | ดูตารางถัดไป |
| [core/keywords.py](../core/keywords.py) | "ลูกค้าพูดถึงบ่อย" (นับคำนามหัวหมวด) | ใช้ `NOUN_TO_ASPECT`; แยกจาก insight |
| [core/insights.py](../core/insights.py) | ข้อสรุปเชิงปฏิบัติ rule-based ราย aspect | กิน `aspect_summary` + `keywords` |
| [core/export.py](../core/export.py) | export CSV/JSON | เรียกจาก routes export |

### core/phrases/ (7 ขั้น + LLM)
| ไฟล์ | ขั้น | บทบาท |
|---|---|---|
| [model.py](../core/phrases/model.py) | — | `Phrase` dataclass ที่ไหลผ่านทุกขั้น |
| [extract.py](../core/phrases/extract.py) | 1 | สกัดวลี: MWE/idiom → ไวยากรณ์เชิงพจนานุกรม (P1–P7) |
| [quality.py](../core/phrases/quality.py) | 2 | กรองวลีขยะ + ตั้ง provisional aspect/conf |
| [canonical.py](../core/phrases/canonical.py) | 3 | สร้าง `canonical`(merge key) + `display`(แสดงผล) + gated synthesis |
| [synonyms.py](../core/phrases/synonyms.py) | 4 | รวมคำพ้องอนุรักษ์นิยม → ตั้ง `agg_key` |
| [aggregate.py](../core/phrases/aggregate.py) | 7 | นับ + จัดอันดับเป็น dashboard contract |
| [llm_extract.py](../core/phrases/llm_extract.py) | (เครื่องยนต์ทางเลือก) | เรียก Claude → map เข้า contract เดิม |

*(ขั้น 5 aspect routing อยู่ใน [aspect.py](../core/aspect.py), ขั้น 6 sentiment อยู่ใน [sentiment.py:127](../core/sentiment.py#L127))*

### templates/ · static/ · data/ · eval/ · scripts/ · docs/
- `templates/`: `base.html` (layout+sidebar+modal+toast), `index`, `dashboard`, `history` (ใช้ซ้ำทั้ง history & saved), `settings`, `error`
- `static/css/style.css`, `static/js/`: common/dashboard/history
- `data/`: `sample_reviews.json` (30), `labeled_reviews.json` (60, gold), `settings.json` (สร้างเมื่อ save, ไม่ commit)
- `eval/`: `evaluate.py` (metrics เอง ไม่พึ่ง sklearn), `label_tool.py`, `report.txt`, `confusion_matrix.csv/png`
- `scripts/compare_engines.py`: เทียบ rule vs LLM
- `docs/superpowers/`: spec + plan ของ 2 ฟีเจอร์

---

## 4. Deep Code Walkthrough

### 4.1 `core/pipeline.py` — orchestrator

**`run_analysis(url, max_reviews=None) -> dict`** ([pipeline.py:71](../core/pipeline.py#L71))
- **จุดประสงค์:** ร้อย 6 ขั้นเป็นผลลัพธ์ก้อนเดียวที่พร้อมเก็บ DB + ส่ง dashboard
- **Return:** dict 11 คีย์ (`store_name`, `engine`, `extract_engine`, `distribution`, `aspect_summary`, `keywords`, `topics`, `insights`, `reviews` ...)
- **Logic:** scrape → preprocess → sentiment.analyze_all → aspect.tag_aspects → distribution + aspect_summary + phrase pipeline + topics + insights
- **Edge case:** ถ้า `total_reviews == 0` (ไม่มีรีวิวไทย) app.py จะ flash error ([app.py:78](../app.py#L78))

**`_rule_phrase_pipeline(reviews) -> dict`** ([pipeline.py:21](../core/pipeline.py#L21))
- วน clause → `detect_clause_aspects` → `extract` → `filter_phrases` → `canonicalize` → `synonyms.aggregate` → `route_aspect` (ถ้ายังไม่มี aspect) → map atmosphere→ambience → `classify_phrase` → เก็บ → `aggregate.build`
- **มี try/except ครอบทั้ง review** ([pipeline.py:38](../core/pipeline.py#L38)) — รีวิวพังตัวเดียวไม่ทำให้ทั้งระบบ 500
- **Time complexity:** O(reviews × clauses × tokens) — ขนาด lexicon คงที่ จึงเป็นเชิงเส้นตามจำนวน token รวม

**`_phrase_pipeline(reviews)`** ([pipeline.py:44](../core/pipeline.py#L44)): dispatch — ถ้า engine=`llm`
และ `llm_extract.available()` → เรียก Claude, ถ้า exception → fallback rule

**`_sentiment_distribution`** ([pipeline.py:55](../core/pipeline.py#L55)): นับ counts + คำนวณ `pct` ด้วย `round(...)`
> ⚠️ **Potential bug:** ผลรวม `round()` ของ 3 ค่าอาจไม่เท่ากับ 100 พอดี (เช่น 33/33/33→99)
> test [test_integration.py:32](../tests/test_integration.py#L32) ยืนยัน ==100 บน sample เฉพาะชุดเท่านั้น
> ไม่ได้รับประกันทั่วไป donut ใน [dashboard.html:83](../templates/dashboard.html#L83) ใช้ขอบเขต
> pos และ pos+neg จึงไม่เพี้ยนทางสายตา แต่ตัวเลขที่แสดงอาจรวมไม่ครบ 100

### 4.2 `core/preprocess.py`

- **`is_thai(text, threshold=0.2)`** ([preprocess.py:44](../core/preprocess.py#L44)): สัดส่วนอักษรไทย ≥ 0.2 → ไทย
- **`clean_text`** ([preprocess.py:53](../core/preprocess.py#L53)): ลบ URL/emoji/อักขระพิเศษ, normalize คำยืดเสียง, lower อังกฤษ
- **`_prepare_clauses`** ([preprocess.py:100](../core/preprocess.py#L100)): ตัดคำทั้งรีวิว**ครั้งเดียว** แล้วแบ่งอนุประโยคที่ระดับ token (กันบั๊ก substring `แต่` ใน `ตกแต่ง`) สร้าง 3 token views: `raw_tokens`(extraction), `tokens`(negation-merged), `tokens_base`(topics)
- **`filter_and_prepare`** ([preprocess.py:118](../core/preprocess.py#L118)): คัดไทย + ตัดรีวิวซ้ำ + guard "never lose a review"
- **Graceful degradation:** ไม่มี PyThaiNLP → fallback ตัดด้วยช่องว่าง + stopword ฮาร์ดโค้ด 20 คำ

### 4.3 `core/negation.py` — แหล่งความจริงเรื่องขั้วคำ

- **`apply_negation(tokens)`** ([negation.py:40](../core/negation.py#L40)): รวม negator + คำขั้วถัดไป**ทันที 1 คำ** → token เดียว
- **`word_polarity(tok)`** ([negation.py:64](../core/negation.py#L64)): +1/-1/0 เข้าใจการพลิกขั้ว ใช้ร่วมทั้ง sentiment และ extract
> **Limitation:** ขอบเขตปฏิเสธมองแค่ token ติดกัน 1 คำ (documented ใน [README.md:308](../README.md#L308))

### 4.4 `core/phrases/extract.py` — Stage 1 (ซับซ้อนที่สุด)

- **`extract(clause)`** ([extract.py:144](../core/phrases/extract.py#L144)): `_match_mwes` (idiom/compound longest-match + overlap suppression) แล้วต่อ `_match_grammar`
- **`_match_grammar`** ([extract.py:81](../core/phrases/extract.py#L81)) มี 4 กฎ: B1 กู้คำประสม (`รอ`+`นาน`→`รอนาน`), B1b negator+descriptor ไร้คำนาม (`ไม่ประทับใจ`), B2 noun-led (P1/P2), B3 standalone descriptor (P7)
- **POS tagging ถูกประเมินแล้วว่าไม่น่าเชื่อถือกับรีวิวไทย จึงเลิกใช้** (docstring [extract.py:3-5](../core/phrases/extract.py#L3-L5))

### 4.5 `core/phrases/quality.py` — Stage 2
**`filter_phrases`** ([quality.py:21](../core/phrases/quality.py#L21)): idiom ผ่านเสมอ, ทิ้ง META_VERBS,
noun+desc ผ่าน, **noun เดี่ยวไร้ desc ทิ้ง**, bare single descriptor conf ต่ำ→ทิ้ง (hallucination guard)

### 4.6 `core/phrases/canonical.py` — Stage 3
**`canonicalize`** ([canonical.py:31](../core/phrases/canonical.py#L31)): แยก `canonical`/`agg_key` (ตัด intensifier
เพื่อนับ) ออกจาก `display` (เก็บคำเดิม `บริการดีมาก`); **gated head-noun synthesis** สังเคราะห์
หัวหมวดเฉพาะ bare lone descriptor conf สูง (`อร่อย`→`อาหารอร่อย`) ไม่เกิด `บริการรอนาน`

### 4.7 `core/sentiment.py`
- **`classify_phrase(phrase)`** ([sentiment.py:127](../core/sentiment.py#L127)): (1) วลีมีขั้วตัวเอง→ใช้ขั้วนั้น
  (`ราคาแพง`=ลบ แม้ในประโยคบวก) (2) วลีกำกวม→**reuse `clause["sentiment"]`** เลี่ยงเรียกโมเดลซ้ำ
- **`engine_name()`** ([sentiment.py:118](../core/sentiment.py#L118)): **รายงานสถานะจริง** ไม่หลอกผู้ใช้

### 4.8 `Phrase` dataclass ([model.py](../core/phrases/model.py))
วัตถุเดียวที่ไหลผ่านทุกขั้น; `clause` back-reference คือสิ่งที่ทำให้ "การสกัด" แยกจาก "การตัดสินอารมณ์" ได้

---

## 5. End-to-End Execution Flow (Step-by-Step)

กรณีโหมด demo (ค่าเริ่มต้น) + กดวิเคราะห์:

1. `GET /` → [index.html](../templates/index.html); base.html inject `demo_mode=True` ([app.py:37](../app.py#L37))
2. กด Analyze → JS `showLoading(true)` → `POST /analyze` พร้อม form `url`
3. [app.py:56 analyze()](../app.py#L56): โหมด demo ข้ามตรวจ URL → `pipeline.run_analysis(url)` ใน try/except
4. `run_analysis`: scraper.fetch_reviews (อ่าน sample) → preprocess.filter_and_prepare → sentiment.analyze_all → aspect.tag_aspects → distribution + aspect_summary + _phrase_pipeline → extract_topics → generate_insights
5. `database.save_analysis(result)` → INSERT + payload JSON, คืน `aid` ([database.py:52](../db/database.py#L52))
6. `redirect → /dashboard/<aid>`
7. [dashboard()](../app.py#L86): `get_analysis(aid)` → render [dashboard.html](../templates/dashboard.html)
8. แสดง metric cards + donut(CSS) + ตารางรีวิว + วลีแยกหมวด + insights; dashboard.js ผูก tab/filter/save/export
9. **Save:** `fetch POST /toggle-save/<id>` → คืน JSON → JS อัปเดต UI

กรณีโหมดจริงต่างที่ขั้น 3-4: ตรวจ `_looks_like_maps_url` → `_fetch_from_apify` (POST sync, รอได้ถึง 300s) และ sentiment เรียก WangchanBERTa

---

## 6. Data Flow Analysis

```
รีวิวดิบ {text, rating, review_date}
  │  scraper.fetch_reviews
  ▼
preprocessed review {text, clean, tokens, tokens_base, clauses[]}
  ▼  แต่ละ clause: {clean, raw_tokens, tokens, tokens_base}
sentiment: ใส่ r["sentiment"] + c["sentiment"]
  ▼
aspect: ใส่ c["aspects"] + r["aspects"]
  ├──────────────► aspect_sentiment_summary  → insights.generate_insights
  ▼
PHRASE PIPELINE (ราย clause):
  raw_tokens ─extract─► Phrase[] ─quality─► ─canonicalize─► ─synonyms─►
   ─route_aspect─► ─classify_phrase─► collected[]
  ▼
aggregate.build → keywords {aspect:{pos/neu/neg:[{word,count}]}}
  ▼
result dict → save_analysis (JSON blob) → get_analysis → dashboard.html
                                                          │
                                          export.py → CSV/JSON
```

**AI data flow (Input → Model → Output):**
- *Sentiment:* `clean text` → WangchanBERTa (truncate 512) → 4 คลาส → `_WISESIGHT_MAP` (question→neutral) → 3 คลาส
- *LLM extraction:* batch reviews → `_build_prompt` → Claude (json_schema) → `_to_contract` → Phrase[] → aggregate.build

---

## 7. Dependency Analysis

| Library | ใช้ทำอะไร | ทำไม | ทางเลือก |
|---|---|---|---|
| Flask 3.1.3 | web framework | เบา, Jinja2 ในตัว | FastAPI/Django (เกินจำเป็น) |
| requests 2.33.1 | เรียก Apify HTTP | client มาตรฐาน | httpx |
| pythainlp 5.3.4 | ตัดคำ/normalize/stopword ไทย | NLP ไทย de-facto; มี fallback | — |
| anthropic >=0.40 | เครื่องยนต์ Claude (optional) | structured output + SDK ทางการ | REST ตรง |
| transformers >=4.40 | โหลด WangchanBERTa | sentiment ไทยแม่นกว่า lexicon | — |
| torch >=2.2 | backend transformers | จำเป็น inference | onnxruntime |
| sentencepiece/protobuf | tokenizer wangchanberta (spm) | จำเป็นต่อโมเดล | — |
| matplotlib | วาด confusion_matrix.png | เสริม eval; ไม่มีก็รันได้ | — |

✅ **ตรวจสอบกับเอกสาร Anthropic ทางการแล้ว:** การเรียก
`client.messages.create(... output_config={"format":{"type":"json_schema","schema":_SCHEMA}})`
ใน [llm_extract.py:114-120](../core/phrases/llm_extract.py#L114-L120) **ถูกต้องตาม API ปัจจุบัน**
(`output_config.format` คือวิธี canonical; `output_format` แบบเก่าถูก deprecate), schema ใช้
`additionalProperties: False` + `required` ครบ, model id `claude-opus-4-8`/`claude-haiku-4-5` valid
การไม่ใช้ adaptive thinking ก็ถูก (spec ระบุว่า extraction นี้ไม่ต้องใช้ thinking) — โค้ดส่วนนี้เขียนได้ดี

---

## 8. Database Analysis

**Schema** ([database.py:34-49](../db/database.py#L34-L49)): ตารางเดียว `analysis`
```
id PK AUTOINCREMENT, store_name, source_url, analyzed_at(ISO),
total_reviews, pct_positive, pct_neutral, pct_negative,
is_saved(0/1, default 0), payload(TEXT = JSON ทั้งก้อน)
```
- **Relationships:** ไม่มี (denormalized โดยตั้งใจ — Phase 1 เก็บ JSON; Phase 2 ค่อยแตกตาราง)
- **Query flow:** `list_*` SELECT คอลัมน์สรุป ORDER BY id DESC LIMIT 50; `get_analysis` `json.loads(payload)`
- **Migration:** ไม่มี framework — แค่ `CREATE TABLE IF NOT EXISTS` เรียกตอน `init_db()` ([app.py:31](../app.py#L31))
- **Indexes:** มีแค่ PK; `is_saved=1` filter ทำ full scan (ข้อมูลน้อย ยอมรับได้)
- **Performance concerns:** SQLite + คอนเนกชันต่อ request (fine single-user; write lock ภายใต้ concurrency); payload JSON → query ราย phrase ไม่ได้; ไม่มี pagination เกิน LIMIT 50

---

## 9. API Analysis

ทุก route อยู่ใน [app.py](../app.py):

| Route | Method | Request | Response | Validation | Error handling |
|---|---|---|---|---|---|
| `/` | GET | — | index.html | — | — |
| `/analyze` | POST | form `url` | redirect / flash | โหมดจริง: url + `_looks_like_maps_url` | try/except กว้าง, 0 รีวิว→flash |
| `/dashboard/<int:aid>` | GET | path aid | dashboard.html | int converter | abort(404) |
| `/history`,`/saved` | GET | — | history.html | — | — |
| `/toggle-save/<int:aid>` | POST | — | JSON `{id,is_saved}` | int converter | คืน False เงียบถ้าไม่พบ |
| `/delete/<int:aid>` | POST | — | JSON `{id,deleted}` | int converter | rowcount>0 |
| `/api/analysis/<int:aid>` | GET | — | **JSON payload เต็ม** | int converter | abort(404) |
| `/settings` | GET/POST | form `engine`,`extract_engine`,`max_reviews` | render / redirect | engine ∈ {rule,llm}, บีบเพดาน | try/except int |
| `/export/<aid>/{reviews,summary}.csv`,`labeling.json` | GET | — | ไฟล์ดาวน์โหลด | abort(404) | — |
| 404/500 | — | — | error.html | — | หน้าเป็นมิตร ไม่โชว์ traceback |

**ข้อสังเกต:** routes ที่เปลี่ยน state เป็น POST แต่**ไม่มี CSRF token** และ**ไม่มี authentication**

---

## 10. AI / Machine Learning Analysis

**(ก) WangchanBERTa (sentiment)** — [sentiment.py](../core/sentiment.py)
- Model: `airesearch/wangchanberta-base-att-spm-uncased` revision `finetuned@wisesight_sentiment` (4 คลาส)
- Logic: pipeline `sentiment-analysis`, ตัด text 512, map `question→neutral`
- Inference: lazy singleton; พังแล้ว fallback lexicon; กันบั๊กเงียบถ้า label แปลก ([sentiment.py:55-61](../core/sentiment.py#L55-L61))

**(ข) Claude LLM extraction** — [llm_extract.py](../core/phrases/llm_extract.py)
- Prompt: system สั้นกระชับ (ดึงคำพูดลูกค้า, ราคา→food, ห้ามแต่งวลี)
- Structured output: JSON schema enum aspect/sentiment + `additionalProperties:false`
- Batch: หลายรีวิวต่อ request, map กลับด้วย index; `available()` เช็คทั้ง key และ import SDK

**(ค) lexicon (fallback / baseline)** — `_predict_lexicon` นับ `word_polarity` + เผื่อ substring

**Evaluation** — [eval/evaluate.py](../eval/evaluate.py): คำนวณ Accuracy/P/R/F1/Macro/Weighted/Confusion/Kappa
เองทั้งหมด ไม่พึ่ง sklearn ผลล่าสุด ([report.txt](../eval/report.txt)): WangchanBERTa Acc 88.3%, Macro-F1 0.879, Kappa 0.825 (60 รีวิว balanced)

---

## 11. Security Review

| ด้าน | สถานะ | รายละเอียด |
|---|---|---|
| Authentication | ❌ ไม่มี | ไม่มีระบบล็อกอิน (โดยตั้งใจ — เครื่องมือเดี่ยว/demo) |
| Authorization | ❌ ไม่มี | ใครก็ดู/ลบ/save analysis ใด ๆ ได้ผ่าน id |
| Input validation | ⚠️ บางส่วน | URL ตรวจคร่าว; int converter; max_reviews บีบช่วง |
| SQL Injection | ✅ ปลอดภัย | parameterized queries ทุกที่ |
| XSS | ✅ ปลอดภัย | Jinja2 autoescape; `{{ a\|tojson }}` escape `<>&` |
| CSRF | ⚠️ เสี่ยง | POST routes ไม่มี token (impact ต่ำ เพราะไม่มี auth/ข้อมูลอ่อนไหว) |
| Secrets exposure | ✅ ดี | key จาก env เท่านั้น, ไม่ commit; debug_apify mask token |
| API key handling | ✅ ดี | `ANTHROPIC_API_KEY` ผ่าน SDK; `APIFY_TOKEN` ผ่าน query param |
| Flask debug | ✅ ดี | ปิดเป็นค่าเริ่มต้น + คอมเมนต์อธิบาย RCE risk |
| SECRET_KEY | ✅ ดี | env ถ้ามี ไม่งั้นสุ่ม + เตือน multi-worker |

**เพิ่มเติม:** Apify token เป็น query param (อาจถูก log โดย proxy — เสี่ยงต่ำ); SSRF เสี่ยงต่ำ
(ส่งให้ Apify + มี guard); DoS: การวิเคราะห์ synchronous ในเธรด request
โดยรวม: เหมาะบริบทโครงงาน/รันเฉพาะที่ **ไม่พร้อม deploy สาธารณะ** ถ้าจะ public ต้องเพิ่ม auth+CSRF+rate-limit+queue

---

## 12. Performance Review

| ประเด็น | การวิเคราะห์ |
|---|---|
| Bottleneck หลัก | โหมดจริง: Apify sync call (timeout 300s) + WangchanBERTa บน CPU; อยู่ในเธรด request เดียว |
| Model inference ซ้ำ | `analyze_all` predict ทั้งรีวิว+ทุก clause; แต่ `classify_phrase` reuse clause cache แล้ว |
| Expensive loops | substring loops ใน detect_aspects / _predict_lexicon — lexicon คงที่ จึง O(n) |
| Unnecessary calls | `get_use_model()` → stat settings.json ต่อรีวิว (มี mtime cache, ต้นทุนน้อย) |
| Memory | payload JSON ทั้งรีวิว — ที่ MAX_REVIEWS=300 ยังเล็ก |
| Scalability | single process; SECRET_KEY สุ่มต่อโปรเซส → multi-worker session พัง; ไม่มี async/queue/cache |
| จุดดี | settings cache by mtime, model singleton, clause sentiment reuse, ตัดคำครั้งเดียว |

---

## 13. Code Quality Review

| มิติ | คะแนน | เหตุผล |
|---|---|---|
| Readability | 9/10 | docstring ไทยอธิบาย "ทำไม"; โครงสร้าง 7 ขั้นเข้าใจง่าย |
| Maintainability | 9/10 | lexicon source of truth จุดเดียว; pure functions; แยก display/agg_key |
| Scalability | 5/10 | พอ single-user; ไม่มี async/queue; SQLite blob |
| Security | 6/10 | พื้นฐานดี แต่ไม่มี auth/CSRF/rate-limit (รับได้ในบริบทโครงงาน) |
| Performance | 6/10 | optimize สำคัญทำแล้ว; แต่ synchronous + CPU model ช้าโหมดจริง |
| Documentation | 9/10 | README + spec/plan ละเอียด เหมาะวิทยานิพนธ์ |
| Testing | 9/10 | **134 tests ผ่านทั้งหมด**, tagger-independent, ครอบทุกขั้น |

**รวมเชิงคุณภาพ: ~8/10** — สูงมากสำหรับโครงงานปริญญาตรี โดดเด่นที่ "อธิบายได้" และวินัยการทดสอบ

---

## 14. Refactoring Opportunities (เรียงตาม Impact)

**Quick Wins:**
1. แก้เอกสารให้ตรงโค้ด — README "108 เทสต์" → จริง **134**; `.env.example` ขาด `ANTHROPIC_API_KEY`/`ANTHROPIC_MODEL`; `MAX_REVIEWS` default ไม่ sync (config 300 / .env.example 100)
2. แก้ percent rounding ใน `_sentiment_distribution` ให้รวมเป็น 100 เสมอ (largest-remainder)
3. ใส่ CSRF protection บน POST routes

**Medium:**
4. ลบ/mark deprecated `clause.split_clauses` (string version ใช้แค่ในเทสต์)
5. แก้ spec รอบแรก (บรรยาย POS-tagging ที่ไม่ได้ implement) ให้มีหมายเหตุ superseded
6. ย้าย `ANTHROPIC_*` config เข้า [config.py](../config.py) ให้รวมศูนย์

**Major:**
7. Async analysis + job queue (แก้ bottleneck synchronous)
8. Phase 2 DB normalization (query/วิเคราะห์ข้ามร้าน)
9. Gold set ราย phrase (วัดคุณภาพ phrase เชิงปริมาณ)

---

## 15. README Verification

README **ตรงกับระบบจริงในระดับสูงมาก** สิ่งที่ตรวจพบ:

**✅ ตรง:** โครงสร้างโฟลเดอร์, ลำดับ pipeline, methodology, ตาราง routes, contract, engine fallback, security notes

**⚠️ ตกหล่น/ไม่ถูกต้อง:**
1. **จำนวนเทสต์:** เขียน "108 เทสต์" ([README.md:265](../README.md#L265)) — จริง **134** (รัน `python -m unittest discover -s tests` → `Ran 134 tests ... OK`)
2. **`.env.example` ไม่ครบ:** README บอกตั้ง `ANTHROPIC_API_KEY`/`ANTHROPIC_MODEL` ใน `.env` และ "ดูค่าทั้งหมดได้ที่ .env.example" ([README.md:76](../README.md#L76)) แต่ [.env.example](../.env.example) **ไม่มี 2 ตัวนี้**
3. **MAX_REVIEWS default ไม่ตรง:** [config.py:41](../config.py#L41) = 300, [.env.example:14](../.env.example#L14) = 100
4. spec รอบแรกบรรยาย POS-tagging ที่ไม่ได้ทำ (README ถูกแล้วว่าเลิกใช้ POS แต่ผู้อ่าน spec อาจสับสน)

---

## 16. Learning Section

**ระบบนี้ทำงานอย่างไร:** ผู้ใช้วาง URL ร้าน → ดึงรีวิว (Apify/demo) → คัดไทย+ทำความสะอาด+ตัดคำ+
**แบ่งอนุประโยค** → จำแนกอารมณ์ (AI/lexicon) → **สกัดวลีความเห็น** 7 ขั้น (หรือ Claude) → จัดหมวด+อารมณ์
→ สรุปข้อเสนอแนะ → แดชบอร์ด + ประวัติ + export

**แนวคิดสำคัญ:** (1) วลีไม่ใช่คำเดี่ยว (2) ระดับอนุประโยค (3) แยกการสกัดจากการตัดสินอารมณ์
(4) display vs agg_key (5) deterministic+อธิบายได้ เลิกใช้ POS (6) เครื่องยนต์คู่+fallback อัตโนมัติ

**เริ่มอ่านไฟล์ตามลำดับ:**
1. [README.md](../README.md) — ภาพรวม + methodology
2. [core/pipeline.py](../core/pipeline.py) — แผนที่ว่าอะไรเรียกอะไร
3. [core/phrases/model.py](../core/phrases/model.py) — `Phrase`
4. [core/lexicon.py](../core/lexicon.py) — **จุดที่ปรับบ่อยที่สุด**
5. [extract.py](../core/phrases/extract.py) → [quality.py](../core/phrases/quality.py) → [canonical.py](../core/phrases/canonical.py) → [aggregate.py](../core/phrases/aggregate.py)
6. [aspect.py](../core/aspect.py) (`route_aspect`) + [sentiment.py](../core/sentiment.py) (`classify_phrase`)
7. [tests/test_integration.py](../tests/test_integration.py)
8. [docs/superpowers/specs/](superpowers/specs/) — เหตุผลเบื้องหลัง (อ่าน spec รอบ 2 เป็นหลัก)

---

## สรุป

InsightReview คุณภาพโค้ดและเอกสารสูงผิดปกติสำหรับโครงงานปริญญาตรี จุดเด่นคือ pipeline สกัดวลี
แบบ deterministic อธิบายได้ทุกขั้น + เครื่องยนต์คู่+fallback + วินัยการทดสอบ

**ความเสี่ยงที่ควรแก้ก่อนสุด (เรียงความสำคัญ):**
1. เอกสารไม่ตรงโค้ด — เลขเทสต์ 108→134, `.env.example` ขาด `ANTHROPIC_*`, MAX_REVIEWS ไม่ sync
2. bug แฝงเรื่อง percent ที่อาจรวมไม่ครบ 100
3. ไม่มี CSRF/auth (รับได้ถ้าไม่ public)
4. สถาปัตยกรรม synchronous ไม่ scale (documented แล้ว)

การเรียก Anthropic API เขียนถูกต้องตามมาตรฐานปัจจุบัน ไม่ต้องแก้
