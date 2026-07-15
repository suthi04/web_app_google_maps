# รายงานเทียบงานวิจัย (เล่ม) ↔ โค้ดจริง — InsightReview

> จัดทำ: 2026-06-27 · branch `feat/review-insight-phrase-extraction`
> ขอบเขต: เทียบเล่มวิทยานิพนธ์ (PDF `UT-Thai-CSIT(JR).pdf`) กับซอร์สโค้ดทั้ง workspace
> วิธี: อ่านโค้ดทุกไฟล์หลัก (`core/`, `app.py`, `db/`, `templates/`, `eval/`, `config.py`) เทียบทีละหัวข้อในเล่ม
> สัญลักษณ์สถานะ: ✅ ตรง · ⚠️ ไม่ตรง/บางส่วน · ➕ โค้ดเพิ่มจากเล่ม · ❌ ยังทำไม่ครบ
> คำแนะนำ 3 แบบ: **1. แก้วิจัย** · **2. แก้โค้ด** · **3. ไม่ต้องแก้**

---

## A. งานวิจัยตรงกับโค้ด ✅ (ไม่ต้องแก้)

| หัวข้อในวิจัย | สถานะ | หลักฐานจากโค้ด | คำแนะนำ |
|---|---|---|---|
| ดึงรีวิวผ่าน Apify (Google Maps Reviews Scraper) | ✅ ตรง | `core/scraper.py:27-30` ใช้ `compass~google-maps-reviews-scraper` | **3. ไม่ต้องแก้** |
| คัดเฉพาะรีวิวภาษาไทย | ✅ ตรง | `core/preprocess.py:44` `is_thai(threshold=0.2)` | **3. ไม่ต้องแก้** |
| คัดกรองรีวิวซ้ำซ้อน | ✅ ตรง | `core/preprocess.py:125-133` `seen` set | **3. ไม่ต้องแก้** |
| Preprocessing: ลบ noise / lowercase / normalize คำยืดเสียง / ตัดคำ / ลบ stopword | ✅ ตรง | `core/preprocess.py:53-77` ครบทุกขั้นตามเล่ม 2.1.2 & 3.1.3 | **3. ไม่ต้องแก้** |
| WangchanBERTa จำแนก 3 คลาส บวก/ลบ/กลาง | ✅ ตรง | `core/sentiment.py:40-62` (4 คลาส → map `question`→neutral) | **3. ไม่ต้องแก้** |
| PyThaiNLP / transformers+torch / requests / google-genai | ✅ ตรง | `requirements*.txt`, `core/preprocess.py:21`, `core/phrases/llm_extract.py` | **3. ไม่ต้องแก้** |
| Gemini = เครื่องมือ**ทางเลือก**สกัดวลี | ✅ ตรง | `core/phrases/llm_extract.py` opt-in + fallback `core/pipeline.py:51-56` | **3. ไม่ต้องแก้** — เล่มเขียน "เครื่องมือทางเลือก" ตรงเป๊ะ |
| Python/Flask + HTML/CSS/JS | ✅ ตรง | `app.py`, `templates/`, `static/js/` | **3. ไม่ต้องแก้** |
| Use Case: ป้อน URL / เริ่มวิเคราะห์ / ดูผล / ดูกราฟ / ดูรายละเอียดรีวิว | ✅ ตรง | `app.py` routes + `templates/dashboard.html` | **3. ไม่ต้องแก้** |
| Flowchart รูป 3.2 (URL→รวบรวม→คัดไทย→ทำความสะอาด→WangchanBERTa→จำแนก→Dashboard) | ✅ ตรง | `core/pipeline.py:87-129` ลำดับตรงกับ flowchart | **3. ไม่ต้องแก้** |
| Donut chart สัดส่วนอารมณ์ | ✅ ตรง | `templates/dashboard.html:87` conic-gradient donut | **3. ไม่ต้องแก้** |
| คำสำคัญแยกหมวด Food/Service/Ambience × บวก/ลบ/กลาง (mockup 3.5–3.9) | ✅ ตรง | `templates/dashboard.html:150-198` + `core/aspect.py` | **3. ไม่ต้องแก้** |
| UI sidebar Dashboard/History/Save + ช่อง URL + ปุ่ม Analyze (mockup 3.3–3.4) | ✅ ตรง | `templates/base.html`, `templates/index.html` | **3. ไม่ต้องแก้** |

---

## B. งานวิจัยไม่ตรงกับโค้ด ⚠️ (ส่วนใหญ่ → แก้วิจัย)

| หัวข้อในวิจัย | สถานะ | หลักฐานจากโค้ด | คำแนะนำ |
|---|---|---|---|
| **Fine-tuning WangchanBERTa ด้วยชุดข้อมูลรีวิวร้านอาหาร** (เล่ม 2.1.3 หน้า 20 ข้อ 2: *"ถูกนำฝึกสอนแบบเฉพาะเจาะจง (Fine-tuning) ด้วยชุดข้อมูลรีวิวร้านอาหาร"*) | ⚠️ **ไม่ตรง (สำคัญสุด)** | `core/sentiment.py:47-51` ใช้ checkpoint `finetuned@wisesight_sentiment` แบบ off-the-shelf — **ไม่มี training script ในโปรเจกต์เลย** | **1. แก้วิจัย** — เปลี่ยนถ้อยคำเป็น "ใช้โมเดล pre-finetuned (Wisesight) แบบ transfer learning" ไม่งั้นถูกกรรมการจับว่าเคลมเกินจริง (ทางเลือก: ไป fine-tune จริงบน Colab ถ้าจะคงคำเดิม) |
| **จัดเก็บข้อมูลในรูปแบบไฟล์ CSV** (ขอบเขต 1.3 ด้านเทคโนโลยี ข้อ 2) | ⚠️ ไม่ตรง | Apify คืน JSON → `db/database.py:52-69` เก็บเป็น **JSON blob ใน SQLite**; CSV มีแค่ตอน export `core/export.py` | **1. แก้วิจัย** — แก้ขอบเขตเป็น "เก็บลง SQLite และส่งออกได้เป็น CSV/JSON" (สอดคล้องกับ 1.7 ที่ระบุ SQLite อยู่แล้ว — เล่มขัดกันเอง) |
| **กราฟแท่ง (Bar Chart) เปรียบเทียบระดับความพึงพอใจ** (เล่ม 2.1.4 หน้า 21) | ⚠️ ไม่ตรง | `templates/dashboard.html` มี donut + แถบ % (track/fill) + metric cards แต่**ไม่มี bar chart เทียบคะแนนดาว/ความพึงพอใจ**; mockup 3.4 ก็ไม่มี | **1. แก้วิจัย** (ลบ/เลี่ยงคำว่า bar chart) **หรือ 2. แก้โค้ด** (เพิ่มกราฟแท่งเทียบ rating) — เลือกอย่างใดอย่างหนึ่งให้ตรงกัน |
| คัดกรองรีวิวที่ "**ผิดปกติ**" (anomaly) ในเบื้องต้น (ขอบเขต 1.3, กรอบ 1.4) | ⚠️ บางส่วน | โค้ดคัดได้แค่: ไม่ใช่ไทย / ว่าง / ซ้ำ (`core/preprocess.py:127-135`) — ไม่มี logic ตรวจ "ผิดปกติ" จริง | **1. แก้วิจัย** — เปลี่ยนเป็น "คัดรีวิวว่าง/ซ้ำ/ไม่ใช่ภาษาไทย" ให้ตรงสิ่งที่ทำจริง |
| ขอบเขตเทคโนโลยีระบุแค่ **HTML/CSS** (1.3 ข้อ 1) | ⚠️ ไม่ครบ | `static/js/*.js` ใช้ JavaScript จริง (dashboard/common/history) | **1. แก้วิจัย** — เพิ่ม JavaScript (1.7 มีแล้ว แต่ 1.3 ตกหล่น) |

---

## C. โค้ดเพิ่มมาจากงานวิจัย ➕ (→ แก้วิจัยให้ครอบคลุม)

| สิ่งที่โค้ดมี (เล่มไม่ได้เขียน) | หลักฐานจากโค้ด | คำแนะนำ |
|---|---|---|
| **ข้อเสนอแนะเชิงปฏิบัติ (Actionable Insights)** — กฎ threshold ราย aspect (จุดแข็ง/ควรปรับปรุง) | `core/insights.py` + `templates/dashboard.html:202-226` | **1. แก้วิจัย** — นี่คือสิ่งที่ทำให้ชื่อเรื่อง "กลยุทธ์" เป็นจริง **ต้องเขียนลงบทที่ 3** (ตอนนี้เล่มไม่มีเลย ทั้งที่เป็น contribution หลัก) |
| **Rule-based phrase pipeline 7 ขั้น** (extract→quality→canonical→synonyms→route→classify→aggregate) | `core/phrases/` + `core/aspect.py route_aspect` | **1. แก้วิจัย** — เล่มพูดถึงแค่ Gemini แต่ตัวจริงที่เป็นค่าเริ่มต้นคือ rule pipeline นี้ ควรอธิบายในบทที่ 3 |
| **จัดการคำปฏิเสธ (negation)** "ไม่+คำขั้ว" | `core/negation.py`, ใช้ใน sentiment/extract | **1. แก้วิจัย** — เพิ่มในวิธีการ (เป็นจุดเด่นภาษาไทย) |
| **แบ่งอนุประโยค (clause split)** | `core/clause.py` `split_clause_tokens` | **1. แก้วิจัย** — เพิ่มในบทที่ 3 |
| **เครื่องยนต์คู่ + fallback อัตโนมัติ** (WangchanBERTa↔lexicon, Gemini↔rule) | `core/sentiment.py:118-124`, `core/pipeline.py:44-56` | **1. แก้วิจัย** — เพิ่มเป็นจุดเด่นเชิงวิศวกรรม |
| **การประเมินผล F1/Kappa/Confusion Matrix** | `eval/evaluate.py`, `eval/report.txt` (Acc 88.3%) | **1. แก้วิจัย** — ใช้เติม **บทที่ 4** (ตอนนี้ว่างเปล่า) |
| **Export CSV/JSON, History/Saved และตัวเลือก engine ข้าง URL** | `core/export.py`, `app.py`, `templates/index.html` | **1. แก้วิจัย** (ทางเลือก) — เพิ่ม use case "บันทึก/ดูประวัติ/เลือกวิธีวิเคราะห์" ถ้าอยากให้ครบ |

---

## D. โค้ดยังทำไม่ครบตามงานวิจัย ❌

| หัวข้อในวิจัย | สถานะ | หลักฐานจากโค้ด | คำแนะนำ |
|---|---|---|---|
| **ทดสอบระบบและประเมินผลจากผู้ใช้งานจริง** (วิธีดำเนินการ 1.7 ข้อ 6 + Gantt ส.ค.–ก.ย.) | ❌ ยังไม่ครบ | มีแต่ unit tests + eval F1 — **ไม่มีแบบประเมินความพึงพอใจ/usability จากเจ้าของร้านจริง** | **2. แก้โค้ด/ทำเพิ่ม** — วางแผนเก็บแบบสอบถามผู้ใช้จริงเพื่อเติมบทที่ 4 มิติ usability |
| **บทที่ 4 (ผลการวิจัย) และบทที่ 5 (สรุป)** | ❌ ว่างเปล่า | เล่มหน้า 34–36 ยังเป็น "เริ่มพิมพ์ที่นี่" | **(งานเขียนเล่ม)** — ดึงจาก `eval/report.txt` + screenshot dashboard จริง |
| กลุ่มผู้ใช้ "**ผู้บริโภคทั่วไป**" (ขอบเขต 1.3 ข้อ 3) | ❌ บางส่วน | ระบบเอนไป B2B (insights สำหรับเจ้าของร้าน); ไม่มีมุมมองสรุปสำหรับผู้บริโภคแยกชัด | **1. แก้วิจัย** หรือ **2. แก้โค้ด** — ปรับขอบเขตให้เน้นเจ้าของร้าน หรือเพิ่มมุมมองผู้บริโภค |

---

## สรุปคำแนะนำเชิงกลยุทธ์

**ส่วนใหญ่ของช่องว่างควร "แก้วิจัยให้ตรงโค้ด" ไม่ใช่แก้โค้ด** เพราะโค้ดทำได้มากกว่าและดีกว่าที่เล่มบรรยาย:

1. โค้ดเสร็จสมบูรณ์ + ผ่าน test 175 ตัว + มีฟีเจอร์เกินเล่ม (insights, phrase pipeline, dual-engine, phrase evaluation) การเขียนเล่มให้ตรงจึงคุ้มกว่าการถอดฟีเจอร์ออก
2. **2 จุดเสี่ยงสูงที่ต้องแก้วิจัยก่อนสอบ**:
   - ① คำว่า **Fine-tuning** (เล่ม 2.1.3) ที่โค้ดไม่ได้ทำ
   - ② **CSV storage** ที่จริงเป็น SQLite
   ทั้งคู่กรรมการจับง่าย

**จุดเดียวที่ควรพิจารณา "แก้โค้ด" จริงจัง** คือ bar chart (เล่ม 2.1.4) — ถ้าอยากคงคำในเล่ม การเพิ่มกราฟแท่งเทียบคะแนนดาวใช้เวลาไม่นานและทำให้ตรงทันที

### ลำดับงานแนะนำ
1. 🔴 แก้เล่ม 2.1.3 เรื่อง fine-tune → transfer learning / pre-finetuned
2. 🔴 แก้ขอบเขต 1.3 เรื่อง CSV → SQLite (+ export CSV/JSON)
3. 🟠 ตัดสินใจ bar chart: ลบออกจากเล่ม **หรือ** เพิ่มในโค้ด
4. 🟠 เขียนบทที่ 3 เพิ่ม: phrase pipeline 7 ขั้น, negation, clause, insights, dual-engine
5. 🟠 เติมบทที่ 4 จาก `eval/report.txt` + screenshot
6. 🟡 แก้ขอบเขตเล็กน้อย: เพิ่ม JavaScript (1.3), แก้คำว่า "ผิดปกติ", ทบทวนกลุ่มผู้ใช้ "ผู้บริโภค"

> อ้างอิงเพิ่มเติมในโปรเจกต์: `docs/RESEARCH-GUIDE.md` (หัวข้อ 9–10 ข้อจำกัด/เช็กลิสต์) และ `docs/ANALYSIS.md` ครอบประเด็น fine-tune และ CSV→SQLite ไว้บางส่วนแล้ว ใช้เป็นฐานเขียนแก้เล่มได้
