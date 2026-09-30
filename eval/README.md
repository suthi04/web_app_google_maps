# Evaluation workspace

โฟลเดอร์นี้เป็นเครื่องมืองานวิจัย ไม่ถูก import โดย Flask runtime

- `evaluate.py`, `label_tool.py` — ประเมินและติด label sentiment ระดับรีวิว
- `challenge_evaluate.py` — วัดชุดท้าทาย 90 ประโยคแยกจากชุดรีวิวจริง
- `build_sentiment_queue.py` — เตรียมรีวิวจริงที่ไม่ซ้ำสำหรับคนติด label (ไฟล์ผลลัพธ์ไม่ขึ้น git)
- `phrase_*.py`, `build_phrase_queue.py` — workflow ติด label/วัดผลระดับ phrase
- `report.txt`, `confusion_matrix.csv`, `confusion_matrix.png` — generated evidence จาก
  `evaluate.py` ซึ่งตั้งใจเก็บไว้เพราะเอกสารวิจัยอ้างผลชุดนี้

ไฟล์ผลลัพธ์สามรายการข้างต้นสร้างใหม่ได้ แต่ไม่ควรลบก่อนอัปเดตบทที่ 4 และหลักฐานผลทดลอง
ให้ตรงกับการรันล่าสุด ส่วนไฟล์ชั่วคราวของ phrase annotation/report ถูก ignore ใน `.gitignore`
เพื่อไม่ให้ข้อมูลระหว่างติด label ปะปนกับ source code

ชุดท้าทายเป็นประโยคที่ผู้พัฒนาเขียนขึ้นและมี provenance ระบุชัด ไม่ใช่รีวิวผู้ใช้จริง
ผล `challenge_*` ใช้วินิจฉัยภาษาสแลง/ประโยคกลางเท่านั้น ห้ามรวมเป็นคะแนนงานวิจัยหลัก

อัปเดต 2026-09-29: ชุดหลักเป็นรีวิวจริง Pupen Seafood 60 รายการ บวก/กลาง/ลบกลุ่มละ 20
ป้ายกำกับโดย AI ก่อนรัน WangchanBERTa และยังรอการตรวจโดยมนุษย์ ผลเบื้องต้น Accuracy 75.0%,
Macro-F1 0.7182, Kappa 0.6250 อ่านวิธีการและข้อจำกัดใน `docs/PUPEN-EVALUATION.md`

- `python -m eval.evaluate --engine model` รันโมเดลจริงและหยุดเมื่อเกิดข้อผิดพลาดโดยไม่ fallback
- `predictions.json` เก็บผลรายรีวิวและ hash ของชุดข้อมูลที่ใช้
- `data/labeled_reviews.json` มีเฉพาะข้อความกับป้าย; ที่มาอยู่ใน `data/labeled_reviews.provenance.json` และถูกตรวจเทียบก่อนรัน
- `collect_pupen_reviews.py` เก็บหลักฐานจาก Apify; การสั่ง `start` เริ่มงานภายนอกและใช้เครดิต
- `build_pupen_dataset.py` ประกอบชุดจากแถวต้นฉบับและป้ายที่คัดก่อนประเมิน
- `data/evaluation_archive/2026-09-29-original/` สำรองชุดเดิมพร้อมรายงานและ Confusion Matrix
