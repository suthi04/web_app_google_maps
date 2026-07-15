# Evaluation workspace

โฟลเดอร์นี้เป็นเครื่องมืองานวิจัย ไม่ถูก import โดย Flask runtime

- `evaluate.py`, `label_tool.py` — ประเมินและติด label sentiment ระดับรีวิว
- `phrase_*.py`, `build_phrase_queue.py` — workflow ติด label/วัดผลระดับ phrase
- `report.txt`, `confusion_matrix.csv`, `confusion_matrix.png` — generated evidence จาก
  `evaluate.py` ซึ่งตั้งใจเก็บไว้เพราะเอกสารวิจัยอ้างผลชุดนี้

ไฟล์ผลลัพธ์สามรายการข้างต้นสร้างใหม่ได้ แต่ไม่ควรลบก่อนอัปเดตบทที่ 4 และหลักฐานผลทดลอง
ให้ตรงกับการรันล่าสุด ส่วนไฟล์ชั่วคราวของ phrase annotation/report ถูก ignore ใน `.gitignore`
เพื่อไม่ให้ข้อมูลระหว่างติด label ปะปนกับ source code
