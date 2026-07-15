# Historical design archive

โฟลเดอร์นี้เก็บ spec และ implementation plan ระหว่างการพัฒนา ไม่ใช่ source of truth
ของระบบปัจจุบัน และไม่มีไฟล์ใดถูก import ตอน runtime

เอกสารควรอ่านตามวันที่ในชื่อไฟล์ เนื่องจากแนวคิดบางส่วนถูกแทนที่ภายหลัง:

- แผนรอบแรกที่กล่าวถึง POS tagging ถูกแทนด้วย lexicon-driven phrase extraction
- แนวคิด Claude ถูกแทนด้วย Gemini
- รายละเอียด route, security, background jobs และจำนวน tests ให้ยึด `README.md`
  กับ `docs/ANALYSIS.md` ปัจจุบัน

เก็บโฟลเดอร์นี้ไว้เพื่ออธิบายเหตุผลและประวัติการตัดสินใจเท่านั้น หากเผยแพร่เฉพาะ
runtime package สามารถตัด `docs/superpowers/` ออกได้ทั้งโฟลเดอร์
