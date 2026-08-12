# InsightReview — รายงานวิเคราะห์ Repository เชิงลึก

> จัดทำครั้งแรก: 2026-06-10 · **ปรับให้ตรงโค้ดปัจจุบัน: 2026-07-14**
> วิธีวิเคราะห์: อ่านทุกไฟล์ใน workspace, รัน test suite จริง (243 เทสต์ ผ่านทั้งหมด), รัน pipeline จริงบนโหมด demo,
> ตรวจ data/spec/plan, และตรวจสอบความถูกต้องของการเรียก Google Gemini API เทียบ SDK ทางการ
> อ้างอิงจากโค้ดจริงทั้งหมด ไม่คาดเดา
>
> **หมายเหตุการปรับปรุง (2026-06-12):** ฉบับเดิม (2026-06-10) บรรยายระบบตอนยังใช้ **Claude (Anthropic)**
> เป็นเครื่องยนต์สกัดวลี และยังมีฟีเจอร์ `topics` ("ลูกค้าพูดถึงบ่อย") + ไฟล์ `core/keywords.py`
> ตั้งแต่นั้น repo ได้: (1) เปลี่ยนเครื่องยนต์ LLM **Claude → Gemini** (`119bfcc`, `bb60aa0` ลบ dependency anthropic)
> (2) ลบฟีเจอร์ topics + `core/keywords.py` (`0d54a9f`) (3) แก้บั๊ก percent ให้รวมเป็น 100 เสมอ (`b665b70`)
> เอกสารฉบับนี้แก้ให้ตรงสถานะปัจจุบันทั้งหมดแล้ว

---

## 1. Project Overview

**InsightReview** คือเว็บแอป (Flask) ที่วิเคราะห์รีวิวร้านอาหารจาก Google Maps แล้วสรุปเป็น
"ข้อมูลเชิงกลยุทธ์" ให้เจ้าของร้าน เป็น**โครงงานปริญญาตรี วท.บ. เทคโนโลยีสารสนเทศ
มหาวิทยาลัยนเรศวร** (ระบุใน [README.md](../README.md))

**ปัญหาที่แก้:** ระบบวิเคราะห์รีวิวทั่วไปมักดึงแค่ "คำเดี่ยว" (`อาหาร`, `ดี`, `อร่อย`)
ซึ่งไม่บอกอะไรที่นำไปใช้ได้ โครงงานนี้ตั้งใจดึง **"วลีความเห็น" (opinion phrases)**
ที่นำไปตัดสินใจได้จริง เช่น `อาหารอร่อย`, `ราคาไม่แพง`, `รอนาน`, `ติดริมน้ำ`
พร้อมจำแนกหมวดและอารมณ์ของแต่ละวลี
(ดูเจตนาใน [docs/.../2026-06-09-review-insight-phrase-extraction-design.md](superpowers/specs/2026-06-09-review-insight-phrase-extraction-design.md))

**กลุ่มผู้ใช้:**
- **ผู้บริโภค** — ดูสิ่งที่ควรรู้ บทสรุปสั้น และข้อควรระวัง
- **เจ้าของ/ผู้จัดการร้านอาหาร** — ดูแดชบอร์ดสรุปอารมณ์ จุดวิกฤต หลักฐาน และกลยุทธ์
- **ผู้ทำวิจัย (ตัวนักศึกษา)** — ใช้ฟังก์ชัน export + eval วัด F1 สำหรับเขียนวิทยานิพนธ์บทที่ 4
- ผู้ใช้เลือก engine/จำนวนรีวิวต่อการวิเคราะห์ข้างช่อง URL ส่วน secret และเพดานอยู่ใน `.env`

**Workflow หลัก** (จาก [app.py](../app.py), [background_jobs.py](../background_jobs.py) และ [core/pipeline.py](../core/pipeline.py)):
```
URL → บันทึก job ใน SQLite → bounded worker queue → scraper (Apify/sample)
→ preprocess (คัดไทย+ตัดคำ+แบ่งอนุประโยค)
→ sentiment (WangchanBERTa/lexicon) → aspect (จัดหมวด)
→ phrase pipeline (สกัดวลี: rule หรือ Gemini) → insights + audience insights
→ เก็บผล SQLite → job completed → browser เปิด dashboard
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
| **External** | Apify (`compass/google-maps-reviews-scraper`), Google Gemini API | [core/scraper.py](../core/scraper.py), [core/phrases/llm_extract.py](../core/phrases/llm_extract.py) |
| **AI/ML** | WangchanBERTa (sentiment), Gemini (phrase extraction), PyThaiNLP (tokenize) | [core/sentiment.py](../core/sentiment.py), [core/phrases/llm_extract.py](../core/phrases/llm_extract.py), [core/preprocess.py](../core/preprocess.py) |
| **3rd-party libs** | Flask, Waitress, requests, pythainlp, google-genai; (optional) transformers, torch, sentencepiece, matplotlib | [requirements.txt](../requirements.txt), [requirements-model.txt](../requirements-model.txt) |

**หัวใจสถาปัตยกรรม:** pipeline แบบ **deterministic 7 ขั้นต่ออนุประโยค** ที่ทุกขั้นเป็น pure
function ทำงานบน `Phrase` dataclass หนึ่งตัว (อธิบายได้ทุกขั้น — สำคัญสำหรับการสอบป้องกัน
วิทยานิพนธ์) มี 2 "เครื่องยนต์" คู่ขนานที่ออกแบบให้ fallback อัตโนมัติ:
- **Sentiment:** WangchanBERTa → fallback lexicon
- **Phrase extraction:** Gemini (LLM) → fallback rule-based

### Text Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          BROWSER (Jinja2 + vanilla JS)                    │
│   index · dashboard(consumer/operator) · history · saved · error          │
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
   scraper ─► preprocess ─► sentiment ─► aspect ─► PHRASE PIPELINE ─► keywords ─► insights
   (Apify/   (clause+      (Wangchan/   (lexicon  ┌─ rule: extract→quality→canonical    │
    sample)   token views)  lexicon)     4-tier)  │   →synonyms→route→classify→aggregate │
                                                  └─ llm: llm_extract (Gemini) ──────────┘
                                          │
       External: ── Apify API ──┐         │ ── Google Gemini API (opt-in) ──┐
                  HuggingFace ───┘ (model) │                                │
                                  lexicon.py = single source of truth (nouns/descriptors/idioms/synonyms)
```

---

## 3. Repository Structure (ไฟล์ต่อไฟล์)

### Root
| ไฟล์ | หน้าที่ | เรียกจาก / ส่งต่อไป |
|---|---|---|
| [app.py](../app.py) | Flask routes ทั้งหมด, จุดเข้าระบบ | import `config`, `core.pipeline`, `core.export`, `db.database` |
| [config.py](../config.py) | ค่ากลางจาก `.env` + ค่าเริ่มต้น compatibility (`data/settings.json`) | ทุกโมดูลเรียกใช้ |
| [background_jobs.py](../background_jobs.py) | bounded worker queue + lifecycle ของงานวิเคราะห์ | เรียก pipeline แล้วอัปเดต `analysis_job` ผ่าน database |
| [serve.py](../serve.py) | production entrypoint แบบ single-process | ให้ Waitress รับ HTTP หลาย threads โดยแชร์ in-process queue เดียว |
| [request_limits.py](../request_limits.py) | sliding-window rate limiter + concurrency gate | `app.py` ใช้ครอบงาน `/analyze` |
| [web_security.py](../web_security.py) | CSRF token + response security headers | Flask before/after request hooks |
| [debug_apify.py](../debug_apify.py) | สคริปต์ตรวจการเชื่อมต่อ Apify 3 ขั้น (token → login → scrape) | สแตนด์อโลน, อ่าน `APIFY_TOKEN` |
| [requirements.txt](../requirements.txt) / [requirements-model.txt](../requirements-model.txt) | dependency เว็บ+demo / +model | — |
| [.env.example](../.env.example) | ตัวอย่าง config (Apify, USE_MODEL, GEMINI_API_KEY/MODEL) | — |

### core/ (ตรรกะวิเคราะห์)
| ไฟล์ | หน้าที่ | ความสัมพันธ์ |
|---|---|---|
| [core/pipeline.py](../core/pipeline.py) | ร้อยทุกขั้น → ผลลัพธ์ 1 dict | เรียกทุกโมดูลใน core; dispatch engine (rule/llm) + รายงาน engine ที่ทำงานจริง |
| [core/scraper.py](../core/scraper.py) | ดึงรีวิว Apify จริง / sample | เรียกจาก pipeline; ใช้ `config.get_apify_token()` เลือกโหมด |
| [core/preprocess.py](../core/preprocess.py) | คัดไทย+ทำความสะอาด+ตัดคำ+แบ่งอนุประโยค (3 token views) | ใช้ `clause`, `negation`; ผลิต `clauses` ที่ไหลต่อ |
| [core/clause.py](../core/clause.py) | แบ่งอนุประโยคตามคำเชื่อมขัดแย้ง (token-level: `split_clause_tokens`) | เรียกจาก preprocess |
| [core/negation.py](../core/negation.py) | รวม "ไม่+คำขั้ว" + แหล่งความจริงเรื่องขั้วคำ (`word_polarity`) | นำเข้า `SENTIMENT_WORDS`; ใช้โดย preprocess/sentiment/extract |
| [core/lexicon.py](../core/lexicon.py) | **★ พจนานุกรมกลาง** (nouns/descriptors/idioms/synonyms) | source of truth ของ aspect, extract, sentiment, keywords |
| [core/sentiment.py](../core/sentiment.py) | จำแนกอารมณ์รีวิว/อนุประโยค + `classify_phrase` | ใช้ lexicon+negation; โหลดโมเดลแบบ lazy singleton |
| [core/aspect.py](../core/aspect.py) | จัดหมวดระดับอนุประโยค + `route_aspect` 4 ชั้น | ใช้ lexicon; เรียกจาก pipeline |
| [core/phrases/](../core/phrases/) | **★ การสกัดวลี (7 ขั้น) + เครื่องยนต์ Gemini** | ดูตารางถัดไป |
| [core/insights.py](../core/insights.py) | ข้อสรุปเชิงปฏิบัติ rule-based ราย aspect | กิน `aspect_summary` + `keywords` |
| [core/audience_insights.py](../core/audience_insights.py) | สรุปผู้บริโภค + จุดวิกฤต/กลยุทธ์ โดยอ้างหลักฐานและไม่เดาชื่อเมนู | กิน reviews/keywords/distribution |
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
| [llm_extract.py](../core/phrases/llm_extract.py) | (เครื่องยนต์ทางเลือก) | เรียก Gemini → map เข้า contract เดิม |

*(ขั้น 5 aspect routing อยู่ใน [aspect.py](../core/aspect.py) `route_aspect`, ขั้น 6 sentiment อยู่ใน [sentiment.py](../core/sentiment.py) `classify_phrase`)*

### templates/ · static/ · data/ · eval/ · scripts/ · docs/
- `templates/`: `base.html` (layout+sidebar+modal+toast), `index`, `job`, `dashboard`, `history` (ใช้ซ้ำทั้ง history & saved), `error`
- `static/css/style.css`, `static/js/`: common/job/dashboard/history
- `data/`: `sample_reviews.json` (30), `labeled_reviews.json` (60, gold), `settings.json` (สร้างเมื่อ save)
- `eval/`: sentiment metrics/label tool + phrase queue/schema/label/agreement/adjudication/dataset split/evaluation/error analysis
- `scripts/compare_engines.py`: เทียบ rule vs LLM (Gemini)
- `docs/superpowers/`: spec + plan ของฟีเจอร์ (review-insight-phrase-extraction, gemini-extraction-engine, hybrid-keyword-extraction)

---

## 4. Deep Code Walkthrough

### 4.1 `core/pipeline.py` — orchestrator

**`run_analysis(url, max_reviews=None, use_model=None, extract_engine=None, progress_callback=None) -> dict`** ([pipeline.py](../core/pipeline.py))
- **จุดประสงค์:** ร้อยทุกขั้นเป็นผลลัพธ์ก้อนเดียวที่พร้อมเก็บ DB + ส่ง dashboard
- **Return:** dict หลัก — `store_name`, `source_url`, `total_reviews`, `fetched_reviews`, `engine`,
  `extract_engine`, `analysis_narrative`, `distribution`, `aspect_summary`, `keywords`, `insights`, `reviews`,
  `consumer_summary`, `critical_issues`, `operator_plan`

`operator_plan` แบ่งข้อมูลเจ้าของร้านเป็น 4 ชั้นที่ไม่ทำหน้าที่ซ้ำกัน: `brief` สรุปทิศทาง,
`items` เป็น Strategic Roadmap รายด้าน, `playbook.risks`/`playbook.opportunities`
เป็นวิธีลงมือทำรายประเด็น และ `next_checks` เป็นเกณฑ์ตรวจผลรอบถัดไป ทุกชั้นอ้างอิง
รหัสรีวิวที่ตรวจย้อนกลับได้ และไม่สรุปตามวันที่ของรีวิว ปัญหาจะได้สถานะ
`ควรจัดการก่อน` เมื่อเสียงลบด้านนั้นอย่างน้อย 40% และมีรีวิวหลักฐานไม่ซ้ำอย่างน้อย
3 รายการ ส่วนโอกาสต่อยอดจะรับเฉพาะคำชมที่มี `evidence_review_ids`
  *(หมายเหตุ: ไม่มี `topics` แล้ว — ฟีเจอร์ "ลูกค้าพูดถึงบ่อย" ถูกถอดออกใน commit `0d54a9f`)*
- **Logic:** scrape → preprocess → sentiment.analyze_all → aspect.tag_aspects → distribution + aspect_summary + phrase pipeline → insights + audience insights
- **Edge case:** ถ้า `total_reviews == 0` (ไม่มีรีวิวไทย) app.py จะ flash error และ redirect กลับหน้าแรก

**`_rule_phrase_pipeline(reviews) -> dict`** ([pipeline.py](../core/pipeline.py))
- วน clause → `detect_clause_aspects` → `extract` → `filter_phrases` → `canonicalize` → `synonyms.aggregate` → `route_aspect` (ถ้ายังไม่มี aspect) → map atmosphere→ambience → `classify_phrase` → เก็บ → `aggregate.build`
- **มี try/except ครอบทั้ง review** — รีวิวพังตัวเดียวไม่ทำให้ทั้งระบบ 500
- **Time complexity:** O(reviews × clauses × tokens) — ขนาด lexicon คงที่ จึงเป็นเชิงเส้นตามจำนวน token รวม

**`_phrase_pipeline(reviews) -> (contract, engine_used, narrative)`** ([pipeline.py](../core/pipeline.py)): dispatch —
ถ้า engine=`llm` และ `llm_extract.available()` → เรียก Gemini หนึ่งครั้งเพื่อรับวลีและ narrative
ที่มี quote อ้างอิง จากนั้นตรวจ quote/index/ตัวเลขและรวมผล Rule-based ที่ยืนยันได้;
ถ้า exception (เช่น โควตา/429) → fallback rule
**คืน `engine_used` เป็นเครื่องยนต์ที่ทำงานจริง** (commit `0c7e016`) — ป้ายผลจึงไม่เคลมเครื่องยนต์ที่ไม่ได้ผลิตวลี

**`_percentages(counts, total)`** ([pipeline.py](../core/pipeline.py)): คำนวณ `pct` แบบจำนวนเต็มด้วย
**largest-remainder method** เพื่อให้ **ผลรวมเป็น 100 เสมอ** (แก้บั๊กเดิมที่ `round()` แยกกันอาจได้ 99/101 — commit `b665b70`)
ตรวจยืนยันด้วยการรันจริง: distribution 57/0/43 → รวม 100

### 4.2 `core/preprocess.py`

- **`is_thai(text, threshold=0.2)`**: สัดส่วนอักษรไทย ≥ 0.2 → ไทย
- **`clean_text`**: ลบ URL/emoji/อักขระพิเศษ, normalize คำยืดเสียง, lower อังกฤษ
- **`_prepare_clauses`**: ตัดคำทั้งรีวิว**ครั้งเดียว** แล้วแบ่งอนุประโยคที่ระดับ token (กันบั๊ก substring `แต่` ใน `ตกแต่ง`) สร้าง 3 token views: `raw_tokens`(extraction), `tokens`(negation-merged), `tokens_base`(aspect detection)
- **`filter_and_prepare`**: คัดไทย + ตัดรีวิวซ้ำ + guard "never lose a review"
- **Graceful degradation:** ไม่มี PyThaiNLP → fallback ตัดด้วยช่องว่าง + stopword ฮาร์ดโค้ด 20 คำ

### 4.3 `core/negation.py` — แหล่งความจริงเรื่องขั้วคำ

- **`apply_negation(tokens)`**: รวม negator + คำขั้วถัดไป**ทันที 1 คำ** → token เดียว
- **`word_polarity(tok)`**: +1/-1/0 เข้าใจการพลิกขั้ว ใช้ร่วมทั้ง sentiment และ extract
> **Limitation:** ขอบเขตปฏิเสธมองแค่ token ติดกัน 1 คำ (documented ใน [README.md](../README.md))

### 4.4 `core/phrases/extract.py` — Stage 1 (ซับซ้อนที่สุด)

- **`extract(clause)`**: `_match_mwes` (idiom/compound longest-match + overlap suppression) แล้วต่อ `_match_grammar`
- **`_match_grammar`** มี 4 กฎ: B1 กู้คำประสม (`รอ`+`นาน`→`รอนาน`), B1b negator+descriptor ไร้คำนาม (`ไม่ประทับใจ`), B2 noun-led (P1/P2), B3 standalone descriptor (P7)
- **POS tagging ถูกประเมินแล้วว่าไม่น่าเชื่อถือกับรีวิวไทย จึงเลิกใช้** (docstring [extract.py](../core/phrases/extract.py))

### 4.5 `core/phrases/quality.py` — Stage 2
**`filter_phrases`**: idiom ผ่านเสมอ, ทิ้ง META_VERBS, noun+desc ผ่าน, **noun เดี่ยวไร้ desc ทิ้ง**,
bare single descriptor conf ต่ำ→ทิ้ง (hallucination guard)

### 4.6 `core/phrases/canonical.py` — Stage 3
**`canonicalize`**: แยก `canonical`/`agg_key` (ตัด intensifier เพื่อนับ) ออกจาก `display` (เก็บคำเดิม `บริการดีมาก`);
**gated head-noun synthesis** สังเคราะห์หัวหมวดเฉพาะ bare lone descriptor conf สูง (`อร่อย`→`อาหารอร่อย`) ไม่เกิด `บริการรอนาน`

### 4.7 `core/sentiment.py`
- **`classify_phrase(phrase)`**: (1) วลีมีขั้วตัวเอง→ใช้ขั้วนั้น (`ราคาแพง`=ลบ แม้ในประโยคบวก)
  (2) วลีกำกวม→**reuse `clause["sentiment"]`** เลี่ยงเรียกโมเดลซ้ำ
- **`engine_name()`**: **รายงานสถานะจริง** (`WangchanBERTa` / `lexicon (พจนานุกรมคำ)` / `lexicon (WangchanBERTa โหลดไม่สำเร็จ)`) ไม่หลอกผู้ใช้

### 4.8 `Phrase` dataclass ([model.py](../core/phrases/model.py))
วัตถุเดียวที่ไหลผ่านทุกขั้น; `clause` back-reference คือสิ่งที่ทำให้ "การสกัด" แยกจาก "การตัดสินอารมณ์" ได้

---

## 5. End-to-End Execution Flow (Step-by-Step)

กรณีโหมด demo (ค่าเริ่มต้น) + กดวิเคราะห์:

1. `GET /` → [index.html](../templates/index.html); base.html inject `demo_mode=True`
2. กด Analyze → JS `showLoading(true)` → `POST /analyze` พร้อม form `url`
3. [app.py](../app.py) `analyze()`: ตรวจ URL/rate-limit/queue capacity → สร้าง `analysis_job` → redirect `/jobs/<job_id>`
4. [background_jobs.py](../background_jobs.py) เปลี่ยนสถานะ queued→running แล้วเรียก `pipeline.run_analysis(url)` นอก HTTP request
5. `run_analysis`: scraper.fetch_reviews → preprocess → sentiment → aspect → distribution/phrase pipeline/insights
6. worker เรียก `database.save_analysis(result)` แล้วเปลี่ยน job เป็น completed พร้อม `analysis_id`
7. pipeline บันทึก progress 7 ขั้นลง SQLite; [job.js](../static/js/job.js) poll ทุก 1.5 วินาที (backoff สูงสุด 15 วินาทีเมื่อเน็ตสะดุด) แสดง progress bar แล้วเปิด URL dashboard ที่ server ส่งมาอัตโนมัติ
8. `dashboard()`: `get_analysis(aid)` → แสดง metric cards + donut + รีวิว + วลี + insights
9. **Save:** `fetch POST /toggle-save/<id>` → คืน JSON → JS อัปเดต UI

กรณีโหมดจริงต่างที่ขั้น 3-4: ตรวจ `_looks_like_maps_url` → `_fetch_from_apify` (POST sync, รอได้ถึง 300s) และ sentiment เรียก WangchanBERTa; ถ้าเลือกเครื่องยนต์ Gemini จะส่งรีวิวทั้งชุดให้ Gemini ในขั้นสกัดวลี

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
aggregate.build → keywords {aspect:{pos/neu/neg:[{word,count,review_count,evidence_review_ids}]}}

`count` คือจำนวน occurrence ของวลี ส่วน `review_count` คือจำนวนรีวิวต้นทางที่ไม่ซ้ำ
และ `evidence_review_ids` ใช้รหัสคงที่รูป `R001` เพื่อย้อนตรวจข้อความเต็มในแดชบอร์ด/ไฟล์ส่งออก
การจัดระดับสัญญาณลบใช้จำนวนรีวิวไม่ซ้ำ ไม่ใช้เปอร์เซ็นต์ลบทั้ง aspect เพื่อยกระดับวลีที่พบครั้งเดียว
  ▼
result dict → save_analysis (JSON blob) → get_analysis → dashboard.html
                                                          │
                                          export.py → CSV/JSON
```

**AI data flow (Input → Model → Output):**
- *Sentiment:* `clean text` → WangchanBERTa (truncate 512) → 4 คลาส → `_WISESIGHT_MAP` (question→neutral) → 3 คลาส
- *LLM extraction (Gemini):* batch reviews → `_build_prompt` → Gemini (`response_schema` JSON) → `_to_contract` → Phrase[] → aggregate.build

---

## 7. Dependency Analysis

| Library | ใช้ทำอะไร | ทำไม | ทางเลือก |
|---|---|---|---|
| Flask 3.1.3 | web framework | เบา, Jinja2 ในตัว | FastAPI/Django (เกินจำเป็น) |
| requests 2.33.1 | เรียก Apify HTTP | client มาตรฐาน | httpx |
| pythainlp 5.3.4 | ตัดคำ/normalize/stopword ไทย | NLP ไทย de-facto; มี fallback | — |
| google-genai >=1.0 | เครื่องยนต์ Gemini (optional) | structured output (`response_schema`) + SDK ทางการ | REST ตรง |
| transformers >=4.40 | โหลด WangchanBERTa | sentiment ไทยแม่นกว่า lexicon | — |
| torch >=2.2 | backend transformers | จำเป็น inference | onnxruntime |
| sentencepiece/protobuf | tokenizer wangchanberta (spm) | จำเป็นต่อโมเดล | — |
| matplotlib | วาด confusion_matrix.png | เสริม eval; ไม่มีก็รันได้ | — |

✅ **ตรวจสอบกับ google-genai SDK แล้ว:** การเรียก
`client.models.generate_content(model=GEMINI_MODEL, contents=..., config={...})`
ใน [llm_extract.py](../core/phrases/llm_extract.py) **ถูกต้องตาม SDK ปัจจุบัน** (ตรวจ signature
`generate_content(self, model, contents, config)` ด้วย `inspect` แล้ว) โดย structured output ใช้
`response_mime_type="application/json"` + `response_schema` (OpenAPI-3 subset) ที่ **ไม่ใส่
`additionalProperties`** — ถูกต้องสำหรับ Gemini (จุดต่างสำคัญจาก Anthropic ที่ต้องใส่
`additionalProperties:false`) schema มี `enum` ของ aspect/sentiment + `required` ครบ;
`available()` เช็คทั้ง API key และ import SDK ก่อนใช้ — โค้ดส่วนนี้เขียนได้ดี

---

## 8. Database Analysis

**Schema** ([database.py](../db/database.py)): ตารางเดียว `analysis`
```
id PK AUTOINCREMENT, store_name, source_url, analyzed_at(ISO),
total_reviews, pct_positive, pct_neutral, pct_negative,
is_saved(0/1, default 0), payload(TEXT = JSON ทั้งก้อน)
```
- **Relationships:** ไม่มี (denormalized โดยตั้งใจ — Phase 1 เก็บ JSON; Phase 2 ค่อยแตกตาราง)
- **Query flow:** `list_*` SELECT คอลัมน์สรุป ORDER BY id DESC LIMIT 50; `get_analysis` `json.loads(payload)`
- **Migration:** ไม่มี framework — แค่ `CREATE TABLE IF NOT EXISTS` เรียกตอน `init_db()`
- **Indexes:** มีแค่ PK; `is_saved=1` filter ทำ full scan (ข้อมูลน้อย ยอมรับได้)
- **Performance concerns:** SQLite + คอนเนกชันต่อ request (fine single-user; write lock ภายใต้ concurrency); payload JSON → query ราย phrase ไม่ได้; ไม่มี pagination เกิน LIMIT 50

---

## 9. API Analysis

ทุก route อยู่ใน [app.py](../app.py):

| Route | Method | Request | Response | Validation | Error handling |
|---|---|---|---|---|---|
| `/` | GET | — | index.html | — | — |
| `/analyze` | POST | form `url`,`engine`,`extract_engine`,`max_reviews` | redirect ไป job / flash | URL + allowlist engine + บีบเพดาน | try/except, 0 รีวิว→job failed |
| `/dashboard/<int:aid>` | GET | path aid | dashboard.html | int converter | abort(404) |
| `/history`,`/saved` | GET | — | history.html | — | — |
| `/toggle-save/<int:aid>` | POST | — | JSON `{id,is_saved}` | int converter | คืน False เงียบถ้าไม่พบ |
| `/delete/<int:aid>` | POST | — | JSON `{id,deleted}` | int converter | rowcount>0 |
| `/api/analysis/<int:aid>` | GET | — | **JSON payload เต็ม** | int converter | abort(404) |
| `/settings` | GET/POST | legacy compatibility | redirect หน้าแรก | engine allowlist, บีบเพดาน | try/except int |
| `/export/<aid>/{reviews,summary}.csv`,`labeling.json` | GET | — | ไฟล์ดาวน์โหลด | abort(404) | — |
| 404/500 | — | — | error.html | — | หน้าเป็นมิตร ไม่โชว์ traceback |

**ข้อสังเกต:** routes ที่เปลี่ยน state ตรวจ CSRF แล้ว แต่ระบบยังไม่มี authentication/
การแยกข้อมูลรายผู้ใช้ตามขอบเขตของโครงงาน

---

## 10. AI / Machine Learning Analysis

**(ก) WangchanBERTa (sentiment)** — [sentiment.py](../core/sentiment.py)
- Model: `airesearch/wangchanberta-base-att-spm-uncased` revision `finetuned@wisesight_sentiment` (4 คลาส)
- Logic: pipeline `sentiment-analysis`, ตัด text 512, map `question→neutral`
- Inference: lazy singleton; พังแล้ว fallback lexicon; กันบั๊กเงียบถ้า label แปลก (เตือนเรื่อง id2label)
- **หมายเหตุ:** ใช้ checkpoint ที่ fine-tune มาแล้วบน Wisesight แบบ off-the-shelf — **ไม่ได้ fine-tune เพิ่มด้วยรีวิวร้านอาหารเอง**

**(ข) Gemini LLM extraction** — [llm_extract.py](../core/phrases/llm_extract.py)
- Prompt: system สั้นกระชับ (ดึงคำพูดลูกค้า, ราคา→food, ห้ามแต่งวลี, วลีสั้น ไม่ใช่ทั้งประโยค)
- Structured output: `response_schema` enum aspect/sentiment + `required` (ไม่ใส่ additionalProperties — ตาม Gemini)
- Batch: หลายรีวิวต่อ request, map กลับด้วย index; กรองวลียาวเกิน 40 อักขระทิ้ง; `available()` เช็คทั้ง key และ import SDK
- **Fallback:** เรียกไม่สำเร็จ/ไม่มี key → กลับไป rule-based อัตโนมัติ (ระบบไม่ล่ม)

**(ค) lexicon (fallback / baseline)** — `_predict_lexicon` นับ `word_polarity` + เผื่อ substring

**Evaluation** — [eval/evaluate.py](../eval/evaluate.py): คำนวณ Accuracy/P/R/F1/Macro/Weighted/Confusion/Kappa
เองทั้งหมด ไม่พึ่ง sklearn ผลล่าสุด ([report.txt](../eval/report.txt)): WangchanBERTa Acc 88.3%, Macro-F1 0.879, Kappa 0.825 (60 รีวิว balanced 20/20/20)

---

## 11. Security Review

| ด้าน | สถานะ | รายละเอียด |
|---|---|---|
| Authentication | — ไม่มีตามขอบเขต | เว็บโครงงานแบบไม่สร้างบัญชีผู้ใช้/ผู้ดูแล |
| Authorization | ⚠️ ข้อมูลร่วม | history/ผลวิเคราะห์เป็นระดับเครื่อง ไม่ได้แยกเจ้าของรายบุคคล |
| Input validation | ✅ ดี | URL ตรวจ scheme/hostname/path และจำกัด 2,048 ตัวอักษร; request ไม่เกิน 1 MiB; env/settings บีบชนิดและช่วง |
| SQL Injection | ✅ ปลอดภัย | parameterized queries ทุกที่ |
| XSS | ✅ ปลอดภัย | Jinja2 autoescape; `{{ a\|tojson }}` escape `<>&` |
| CSRF | ✅ ปลอดภัย | POST/PUT/PATCH/DELETE ตรวจ token จาก form หรือ `X-CSRF-Token` ทุก route |
| Secrets exposure | ✅ ดี | key จาก env เท่านั้น, ไม่ commit; debug_apify mask token |
| API key handling | ✅ ดี | `GEMINI_API_KEY` อ่านสดผ่าน `get_gemini_api_key()`; `APIFY_TOKEN` ผ่าน query param |
| Privacy (LLM) | ⚠️ พึงระวัง | โหมด Gemini ส่งข้อความรีวิวออกไปยัง Google (เป็น opt-in; rule-based ทำงานออฟไลน์) |
| Abuse control | ✅ ระดับ single process | `/analyze` จำกัดต่อ IP พร้อม `Retry-After` และมี concurrency gate; ปิด/ปรับผ่าน env ได้ |
| Browser policy | ✅ ดี | `HttpOnly`, `SameSite=Lax`, CSP, no-store, nosniff, frame deny, referrer/permissions/COOP headers |
| Flask debug | ✅ ดี | ปิดเป็นค่าเริ่มต้น + คอมเมนต์อธิบาย RCE risk |
| SECRET_KEY | ✅ ดี | env ถ้ามี ไม่งั้นสุ่ม + เตือน multi-worker |

**เพิ่มเติม:** Apify token เป็น query param (อาจถูก log โดย proxy — เสี่ยงต่ำ); SSRF เสี่ยงต่ำ
(ส่งให้ Apify + มี guard); งานหนักอยู่นอก request thread และคิวมีขนาดจำกัด
โดยรวม: พร้อมขึ้น staging/ใช้สาธิตแบบไม่ล็อกอิน; หากรันหลาย process ต้องย้าย queue coordination/rate-limit ไป Redis/Celery/RQ และพิจารณาการแยกข้อมูลผู้ใช้

---

## 12. Performance Review

| ประเด็น | การวิเคราะห์ |
|---|---|
| Bottleneck หลัก | โหมดจริง: Apify sync call (timeout 300s) + WangchanBERTa บน CPU; รันใน bounded background worker |
| Model inference | `analyze_all` รวมทั้งรีวิว+ทุก clause เป็น batch เดียว; `classify_phrase` reuse clause cache แล้ว |
| Expensive loops | substring loops ใน detect_aspects / _predict_lexicon — lexicon คงที่ จึง O(n) |
| Unnecessary calls | `get_use_model()` → stat settings.json ต่อรีวิว (มี mtime cache, ต้นทุนน้อย) |
| Memory | payload JSON ทั้งรีวิว — ที่ MAX_REVIEWS=100 ยังเล็ก |
| Scalability | มี async job UI/queue ภายในโปรเซส; หากหลาย process ต้องใช้ external broker/shared limiter |
| จุดดี | request ตอบเร็ว, job state คงอยู่ใน SQLite, queue bounded, recovery หลัง restart, batch inference, settings/DB lifecycle แข็งแรง |

---

## 13. Code Quality Review

| มิติ | คะแนน | เหตุผล |
|---|---|---|
| Readability | 9/10 | docstring ไทยอธิบาย "ทำไม"; โครงสร้าง 7 ขั้นเข้าใจง่าย |
| Maintainability | 9/10 | lexicon source of truth จุดเดียว; pure functions; แยก display/agg_key |
| Scalability | 7/10 | มี bounded async queue และ persistent status; ยังไม่ใช่ distributed queue |
| Security | 8/10 | มี analysis rate-limit/concurrency gate, CSRF, input guard และ cookie/browser headers; ไม่มีการแยกสิทธิ์ผู้ใช้ตามขอบเขต |
| Performance | 7/10 | งานหนักไม่ค้าง request และ batch inference แล้ว; CPU model/Apify ยังเป็น bottleneck |
| Documentation | 9/10 | README + spec/plan ละเอียด เหมาะวิทยานิพนธ์ |
| Testing | 9/10 | **243 tests ผ่านทั้งหมด**, รวม audience views/evidence traceability/async demo E2E/background jobs/request guards/accessibility/phrase evaluation/security/config/DB/Apify boundaries |

**รวมเชิงคุณภาพ: ~8/10** — สูงมากสำหรับโครงงานปริญญาตรี โดดเด่นที่ "อธิบายได้" และวินัยการทดสอบ

---

## 14. Refactoring Opportunities (เรียงตาม Impact)

**Quick Wins:**
1. เพิ่ม shared broker (Redis/Celery/RQ) หากจะรันหลาย process/หลายเครื่อง
2. เพิ่มการประมาณเวลาคงเหลือจากสถิติ duration ของแต่ละ stage หากมีข้อมูลใช้งานจริงเพียงพอ

**Medium:**
3. ย้าย config ที่เกี่ยวกับ Gemini ให้รวมศูนย์ใน [config.py](../config.py) ครบถ้วน (ปัจจุบัน `GEMINI_MODEL` อยู่ใน config แล้ว, key อ่านสดผ่าน `get_gemini_api_key()`)
4. ทบทวน spec รอบแรกที่บรรยาย POS-tagging (ไม่ได้ implement) ให้มีหมายเหตุ superseded

**Major:**
5. Phase 2 DB normalization (query/วิเคราะห์ข้ามร้าน)
6. ติด label phrase gold set 2 คน + adjudicate (framework/metrics พร้อมแล้ว แต่ยังห้ามอ้าง Phrase F1 ก่อนมี gold จริง)

> **หมายเหตุ:** รายการ refactor ในฉบับเดิมหลายข้อ **ทำเสร็จแล้ว** — percent rounding (largest-remainder, `b665b70`),
> ลบ topics/`keywords.py` (`0d54a9f`), ลบ `clause.split_clauses` แบบ string (เหลือแค่ `split_clause_tokens`),
> `.env.example` เพิ่ม Gemini + sync `MAX_REVIEWS=100` แล้ว จึงถอดออกจากรายการนี้

---

## 15. README Verification

README **ตรงกับระบบจริงในระดับสูงมาก** หลังการอัปเดตล่าสุด:

**✅ ตรง:** โครงสร้างโฟลเดอร์, ลำดับ pipeline, methodology, ตาราง routes, contract, engine fallback,
security notes, **จำนวนเทสต์ 243** (รัน `python -m unittest discover -s tests` → `Ran 243 tests ... OK`),
`.env.example` มี `GEMINI_API_KEY`/`GEMINI_MODEL` ครบ, `MAX_REVIEWS` default 100 ตรงกันทั้ง config และ .env.example,
เครื่องยนต์ LLM = Gemini ตรงทั้ง README/โค้ด/requirements

**⚠️ จุดที่ผู้อ่านควรทราบ:**
- spec รอบแรก (`2026-06-09`) บรรยาย POS-tagging ที่ภายหลังเลิกใช้ และ spec `gemini-extraction-engine` มาทีหลัง —
  ควรอ่าน spec ตามลำดับเวลาเพื่อไม่สับสนว่าระบบเคยใช้ Claude มาก่อน
- README ระบุ WangchanBERTa เป็นโหมดวิจัย (opt-in) ส่วนค่าเริ่มต้นของโค้ดคือ lexicon — ตรงกับ config

---

## 16. Learning Section

**ระบบนี้ทำงานอย่างไร:** ผู้ใช้วาง URL ร้าน → ดึงรีวิว (Apify/demo) → คัดไทย+ทำความสะอาด+ตัดคำ+
**แบ่งอนุประโยค** → จำแนกอารมณ์ (AI/lexicon) → **สกัดวลีความเห็น** 7 ขั้น (หรือ Gemini) → จัดหมวด+อารมณ์
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
8. [docs/superpowers/specs/](superpowers/specs/) — เหตุผลเบื้องหลัง

---

## สรุป

InsightReview คุณภาพโค้ดและเอกสารสูงผิดปกติสำหรับโครงงานปริญญาตรี จุดเด่นคือ pipeline สกัดวลี
แบบ deterministic อธิบายได้ทุกขั้น + background progress job + เครื่องยนต์คู่ (WangchanBERTa↔lexicon, Gemini↔rule) + fallback + วินัยการทดสอบ (243 เทสต์)

**ความเสี่ยงที่ควรพิจารณา (เรียงความสำคัญ):**
1. การจำแนกอารมณ์ใช้ checkpoint Wisesight แบบ off-the-shelf (ไม่ได้ fine-tune เฉพาะโดเมนรีวิวร้านอาหาร) — เป็นข้อจำกัดที่ควรระบุในเล่ม
2. เครื่องมือ phrase-level evaluation พร้อมแล้ว แต่ gold set ยังต้องติด label อิสระ 2 คนและ adjudicate
3. ไม่มี authentication/การแยกข้อมูลรายผู้ใช้ และโหมด Gemini ส่งข้อมูลออกภายนอก (มี disclosure และเป็น opt-in)
4. background queue ปัจจุบันอยู่ในโปรเซสเดียว; ถ้ารันหลาย worker ต้องใช้ external broker

การเรียก Google Gemini API เขียนถูกต้องตาม SDK ปัจจุบัน (`client.models.generate_content` + `response_schema`) ไม่ต้องแก้
