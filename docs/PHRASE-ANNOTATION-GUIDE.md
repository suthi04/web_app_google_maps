# คู่มือติด Label วลีความคิดเห็น — InsightReview

เอกสารนี้กำหนดมาตรฐานสำหรับสร้าง phrase-level gold set เพื่อประเมินการสกัดวลี,
การจัดหมวด และอารมณ์ โดยผู้ติด label สองคนต้องทำงานอย่างอิสระก่อน adjudication

## หน่วยที่ติด Label

เลือกช่วงข้อความที่สั้นที่สุดซึ่งยังสื่อ “หัวข้อ + ความเห็น” ได้ครบ เช่น:

- `อาหารอร่อยมาก` → food / positive
- `ราคาไม่แพง` → food / positive
- `บริการช้า` → service / negative
- `บรรยากาศคึกคัก` → ambience / neutral หรือ positive ตามบริบท

กติกา:

1. คัดลอกข้อความตรงจากรีวิว ห้ามสร้างคำนามที่ต้นฉบับไม่มี
2. เก็บคำปฏิเสธและคำขยายที่เปลี่ยนความหมาย เช่น `ไม่`, `มาก`, `เกินไป`
3. หากประโยคมีหลายความคิดเห็น ให้แยกหลายวลี
4. ไม่ติด label คำนามล้วน เช่น `อาหาร`, `พนักงาน`, `ร้าน`
5. ไม่ติด label ข้อความที่ไม่มีการประเมิน เช่น เวลาเปิดร้านหรือที่อยู่
6. วลีซ้อนกันได้เฉพาะเมื่อเป็นคนละความคิดเห็นจริง ห้ามทำ duplicate span+label

## หมวด

| ค่า | ความหมาย |
|---|---|
| `food` | อาหาร รสชาติ วัตถุดิบ ปริมาณ เมนู ราคา และความคุ้มค่า |
| `service` | พนักงาน การรอ คิว การเสิร์ฟ ออเดอร์ และการชำระเงิน |
| `ambience` | บรรยากาศ ความสะอาด พื้นที่ แอร์ เสียง วิว ห้องน้ำ และที่จอดรถ |

## อารมณ์

| ค่า | เกณฑ์ |
|---|---|
| `positive` | ชม พอใจ แนะนำ หรือปฏิเสธคำลบ เช่น `ไม่แพง` |
| `negative` | ตำหนิ ไม่พอใจ หรือปฏิเสธคำบวก เช่น `ไม่อร่อย` |
| `neutral` | กล่าวถึงโดยไม่มีขั้วชัด หรือข้อเท็จจริงที่ยังเป็นวลีความคิดเห็นตามบริบท |

## Workflow ที่ทำซ้ำได้

```bash
# 1) สร้างคิวแบบ deterministic จาก SQLite + fixtures (ไม่เรียก API)
python -m eval.build_phrase_queue --seed 2026

# 2) ผู้ติด label สองคนทำอย่างอิสระ
python -m eval.phrase_label_tool --annotator annotator_a
python -m eval.phrase_label_tool --annotator annotator_b

# 3) วัดข้อตกลงก่อนเห็นคำตอบของอีกฝ่าย
python -m eval.phrase_agreement \
  data/phrase_annotations_annotator_a.json \
  data/phrase_annotations_annotator_b.json

# 4) ตัดสินข้อขัดแย้งเป็น gold set
python -m eval.phrase_adjudicate \
  data/phrase_annotations_annotator_a.json \
  data/phrase_annotations_annotator_b.json \
  --output data/phrase_gold.json

# 5) ตรวจ distribution และแบ่ง train/dev/test แบบ deterministic
python -m eval.phrase_dataset data/phrase_gold.json --split-dir data/phrase_splits

# 6) ประเมิน rule และ Gemini บน gold เดียวกัน
python -m eval.phrase_evaluate data/phrase_gold.json --engine rule
python -m eval.phrase_evaluate data/phrase_gold.json --engine llm --llm-batch-size 25

# 7) สร้างรายการ error สำหรับวิเคราะห์เชิงคุณภาพ
python -m eval.phrase_error_analysis data/phrase_gold.json --engine rule
```

รายงานมีทั้ง Exact span F1, Partial span F1 ที่ IoU ≥ 0.5, Aspect/Sentiment/Joint
end-to-end F1, classification Macro-F1 บน span ที่ match และจำนวน prediction ที่
ย้อนตำแหน่งกลับไปยังข้อความต้นฉบับไม่ได้

`phrase_dataset.py` ตรวจจำนวน/การกระจายวลีและป้องกัน review id เดียวกันรั่วข้าม split
ส่วน `phrase_error_analysis.py` แยก false positive, false negative, boundary, aspect,
sentiment และ joint-label error เพื่อใช้เขียน Error Analysis ในบทที่ 4

## ข้อกำหนดก่อนใช้อ้างอิงในงานวิจัย

- ห้ามใช้ผลที่โมเดลสร้างเองเป็น gold label
- ผู้ติด label ต้องไม่เห็น prediction ของระบบระหว่างติด label
- รายงานจำนวนรีวิว จำนวนวลี การกระจายหมวด และการกระจายอารมณ์
- รายงาน agreement ก่อน adjudication
- แยกชุดที่ใช้ปรับ lexicon ออกจาก test set สุดท้าย
- เก็บ `schema_version`, `guideline_version`, seed และไฟล์ gold ที่ใช้สร้างตัวเลขทุกครั้ง
