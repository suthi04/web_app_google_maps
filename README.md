# InsightReview

เว็บแอปวิเคราะห์รีวิวร้านอาหารจาก Google Maps → จำแนกอารมณ์ (บวก/กลาง/ลบ) ด้วย WangchanBERTa → แยกคุณลักษณะ (อาหาร/บริการ/บรรยากาศ) → สรุปคำสำคัญ → แดชบอร์ด + ข้อสรุปเชิงปฏิบัติ

โครงงาน วท.บ. เทคโนโลยีสารสนเทศ มหาวิทยาลัยนเรศวร

---

## ✨ จุดสำคัญ: รันได้ทันทีด้วย "โหมด demo"

โค้ดนี้ออกแบบให้ **รันได้เลยโดยไม่ต้องมี Apify token และไม่ต้องโหลดโมเดล** — เหมาะกับการพัฒนา UI และทดสอบ flow ทั้งหมด

```bash
# 1) ติดตั้ง dependency (เบา)
pip install -r requirements.txt

# 2) รัน
python app.py

# 3) เปิดเบราว์เซอร์
#    http://127.0.0.1:5000
#    วาง URL ร้านอะไรก็ได้ (โหมด demo จะใช้ข้อมูลตัวอย่างแทน) แล้วกด Analyze
```

โหมด demo จะ:
- ใช้รีวิวตัวอย่าง 30 รายการใน `data/sample_reviews.json` (ร้าน "ครัวบ้านสวน") แทนการเรียก Apify
- วิเคราะห์อารมณ์ด้วย **lexicon** (พจนานุกรมคำบวก/ลบ) แทน WangchanBERTa
- ทำงานครบทุกขั้นตอนที่เหลือเหมือนจริง (aspect, keyword, insight, dashboard, history, save)

> มี badge บนแดชบอร์ดบอกว่ากำลังใช้ engine อะไร (`lexicon (demo)` หรือ `WangchanBERTa`)

---

## 🚀 เปิด "โหมดจริง" (ทำเมื่อพร้อม)

ทั้งสองส่วนเปิดแยกกันได้อิสระ — จะเปิดแค่ Apify, แค่โมเดล, หรือทั้งคู่ก็ได้

### (ก) ดึงรีวิวจริงจาก Google Maps ด้วย Apify
1. สมัคร [Apify](https://apify.com) (ฟรี เครดิต $5/เดือน ≈ 20,000 รีวิว)
2. คัดลอก API token จาก Apify Console → Settings → Integrations
3. ตั้งค่า:
   ```bash
   export APIFY_TOKEN=apify_api_xxxxxxxxxxxxx
   export MAX_REVIEWS=300
   python app.py
   ```
> ⚠️ ต้องตรวจชื่อ field ของ actor ที่ใช้ใน `core/scraper.py` ให้ตรงกับ actor จริง (เช่น `startUrls`, `maxReviews`) เพราะแต่ละ actor ตั้งชื่อ input ไม่เหมือนกัน — ดูคอมเมนต์ในไฟล์

### (ข) ใช้ WangchanBERTa วิเคราะห์อารมณ์จริง
1. ติดตั้งโมเดล (หนักหน่อย ~2GB):
   ```bash
   pip install -r requirements-model.txt
   ```
2. ตั้งค่า:
   ```bash
   export USE_MODEL=1
   python app.py
   ```
> โมเดลจะถูกดาวน์โหลดอัตโนมัติครั้งแรก ใช้ `airesearch/wangchanberta-base-att-spm-uncased`
> revision `finetuned@wisesight_sentiment` (4 คลาส — โค้ดแมป "question" → neutral ให้แล้ว)
> รันบน CPU ได้แต่ช้า ถ้าจะ **fine-tune** ให้ทำบน Google Colab

ดูค่าทั้งหมดได้ที่ `.env.example`

---

## 🗂 แผนผังโค้ด (ไว้ปรับเองง่าย ๆ)

```
insightreview/
├── app.py                 # Flask: route ทั้งหมด (/, /analyze, /dashboard, /history, /saved, ...)
├── config.py              # ค่ากลาง อ่านจาก env (สลับ demo/real ที่นี่)
│
├── core/                  # ตรรกะการวิเคราะห์ (แก้ส่วนนี้เพื่อปรับคุณภาพผลลัพธ์)
│   ├── scraper.py         #  - ดึงรีวิว: Apify จริง / sample เมื่อ demo
│   ├── preprocess.py      #  - ทำความสะอาด + ตัดคำไทย (PyThaiNLP, มี fallback)
│   ├── sentiment.py       #  - จำแนกอารมณ์: WangchanBERTa / lexicon เมื่อ demo
│   ├── lexicon.py         #  - ★ พจนานุกรม aspect + คำบวก/ลบ (เพิ่มคำที่นี่)
│   ├── aspect.py          #  - จับหมวด อาหาร/บริการ/บรรยากาศ
│   ├── keywords.py        #  - สกัดคำสำคัญด้วย TF-IDF (ดึงคำเด่นเฉพาะร้าน)
│   ├── export.py          #  - ส่งออกผลเป็น CSV / JSON (สำหรับงานวิจัย)
│   ├── insights.py        #  - ★ สร้างข้อสรุปเชิงปฏิบัติ (rule-based, ปรับ threshold ได้)
│   └── pipeline.py        #  - ร้อยทุกขั้นตอนเข้าด้วยกัน → ผลลัพธ์ 1 ก้อน
│
├── db/
│   └── database.py        # SQLite: บันทึก/ดึงผลวิเคราะห์ + History + Save
│
├── templates/             # หน้าเว็บ (Jinja2)
│   ├── base.html          #  - โครง: sidebar + topbar
│   ├── index.html         #  - หน้าแรก (กรอก URL)
│   ├── dashboard.html     #  - แดชบอร์ด (การ์ดอารมณ์ + donut + ตาราง + insight)
│   └── history.html       #  - History / Saved
│
├── static/
│   ├── css/style.css      # ธีมตาม mockup (donut เป็น CSS ล้วน ไม่พึ่ง CDN)
│   └── js/dashboard.js    # สลับแท็บ All/Keywords + filter อารมณ์ + ปุ่ม save
│
├── data/sample_reviews.json   # ข้อมูลตัวอย่างสำหรับโหมด demo
├── data/labeled_reviews.json  # ชุดทดสอบ gold standard (ติด label มือ)
├── eval/                       # การประเมินผลโมเดล
│   ├── evaluate.py             #  - คำนวณ F1 / confusion matrix / kappa
│   └── label_tool.py           #  - เครื่องมือช่วยติด label เพิ่ม
├── requirements.txt           # demo mode
├── requirements-model.txt     # + WangchanBERTa
└── .env.example               # ตัวอย่างค่า env
```

จุดที่มัก "ปรับบ่อย":
- **`core/lexicon.py`** → เพิ่มคำในพจนานุกรม aspect ให้จับหมวดได้แม่นขึ้น
- **`core/insights.py`** → ปรับ threshold / ข้อความข้อเสนอแนะ
- **`static/css/style.css`** → ปรับหน้าตาให้ตรง mockup เป๊ะขึ้น

---

## 🔬 ขั้นตอนทำวิจัยแบบครบวงจร (แนะนำสำหรับเล่ม)

```
1) วิเคราะห์ร้านจริง (ตั้ง APIFY_TOKEN) -> ได้ dashboard + เก็บลง DB
2) บนหน้า dashboard กดปุ่ม Export:
     - "รีวิวทั้งหมด (CSV)"  -> ใส่ภาคผนวก / ตรวจสอบผลด้วยตา
     - "สรุปผล (CSV)"        -> ตารางสถิติลงเล่ม
     - "รีวิวสำหรับติด label (JSON)" -> เอาไปสร้างชุดทดสอบจากข้อมูลจริง
3) ติด label ข้อมูลจริง:  python eval/label_tool.py for_labeling_1.json
4) วัดผลโมเดล:            USE_MODEL=1 python eval/evaluate.py
     -> ได้ Accuracy / F1 / confusion matrix / kappa จากข้อมูลจริงของคุณเอง
```

> การวัด F1 บน "รีวิวจริงของร้านที่ใช้ในเล่ม" น่าเชื่อถือกว่าชุดตัวอย่าง และตอบกรรมการได้ตรงคำถาม

---

## 📊 การประเมินผลโมเดล (สำหรับบทที่ 4)

มีชุดประเมินผลพร้อมใช้ที่โฟลเดอร์ `eval/` — ให้หลักฐานเชิงปริมาณว่าโมเดลแม่นแค่ไหน

```bash
python eval/evaluate.py                # ประเมิน engine ปัจจุบัน (demo = lexicon)
USE_MODEL=1 python eval/evaluate.py    # ประเมิน WangchanBERTa จริง
```

จะได้: Accuracy, Precision/Recall/F1 รายคลาส, Macro/Weighted-F1, Confusion Matrix และ
Cohen's Kappa — พิมพ์ออกจอ + บันทึก `eval/report.txt`, `eval/confusion_matrix.csv`
(และ `confusion_matrix.png` ถ้ามี matplotlib)

ชุดทดสอบ gold standard อยู่ที่ `data/labeled_reviews.json` (ติด label มือ 60 รายการ)
**ก่อนสอบจริงควรขยายเป็น ~400 รายการ** ด้วยเครื่องมือช่วย:

```bash
python eval/label_tool.py              # ติด label เพิ่มทีละรีวิว (p/u/n/s/q)
```

---

## ✅ ทำเสร็จแล้ว
- [x] ดึงรีวิว (Apify จริง + โหมด demo)
- [x] คัดเฉพาะภาษาไทย + ทำความสะอาด + ตัดคำ
- [x] จำแนกอารมณ์ 3 คลาส (WangchanBERTa + lexicon fallback)
- [x] จับ aspect อาหาร/บริการ/บรรยากาศ
- [x] สกัดคำสำคัญด้วย **TF-IDF** (ดึงคำเด่นเฉพาะร้าน)
- [x] ข้อสรุปเชิงปฏิบัติ (rule-based)
- [x] แดชบอร์ด + History + Search/Sort/Delete + Save
- [x] **Error handling** (try/except, ตรวจ URL, หน้า error, flash→toast)
- [x] **Export** ผลวิเคราะห์เป็น CSV (รีวิว+สรุป) และ JSON สำหรับติด label
- [x] **ชุดประเมินผล F1 + confusion matrix + Cohen's Kappa**

## 🔜 ทำต่อ
- [ ] ขยายชุดทดสอบเป็น ~400 รีวิว (ใช้ `eval/label_tool.py`) แล้วรายงานผลจริง
- [ ] (ถ้าผล F1 ต่ำ) fine-tune WangchanBERTa บน Colab
- [ ] export ผลเป็น PDF/Excel, แบ่งหน้า (pagination) ใน History
- [ ] ประเมินการใช้งานจริงด้วยแบบสอบถาม SUS

---

## หมายเหตุ
- ฐานข้อมูล `insightreview.db` ถูกสร้างอัตโนมัติเมื่อรันครั้งแรก
- โหมด demo ออกแบบให้ทดสอบ UI/flow ได้โดยไม่มีค่าใช้จ่ายและไม่ต้องต่อเน็ตหนัก
- การวิเคราะห์จริง 1 ครั้งอาจใช้เวลาหลายสิบวินาทีถึงไม่กี่นาที (รอ Apify + โมเดลบน CPU) — ควรเพิ่ม UX แสดงสถานะกำลังโหลดเมื่อขึ้นโหมดจริง
