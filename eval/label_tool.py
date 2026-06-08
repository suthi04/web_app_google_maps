"""
eval/label_tool.py
==================
เครื่องมือช่วยติด label รีวิวด้วยมือแบบเร็ว ๆ เพื่อขยายชุดทดสอบ
จาก 60 -> ~400 รายการ (ยิ่งเยอะ ผล F1 ยิ่งน่าเชื่อถือ)

วิธีรัน (จาก root ของโปรเจกต์):
    python eval/label_tool.py                      # ดึงข้อความจาก data/sample_reviews.json
    python eval/label_tool.py path/to/texts.json   # หรือระบุไฟล์เอง (list ของ string หรือ {"text": ...})

ระหว่างติด label จะถามทีละรีวิว กดปุ่ม:
    p = positive   u = neutral   n = negative   s = ข้าม   q = บันทึกแล้วออก

ผลจะถูก "เพิ่มต่อท้าย" ใน data/labeled_reviews.json (ข้ามข้อความที่ติด label แล้ว)
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LABELED = os.path.join(ROOT, "data", "labeled_reviews.json")
KEYMAP = {"p": "positive", "u": "neutral", "n": "negative"}


def load_texts(src):
    with open(src, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "reviews" in data:
        data = data["reviews"]
    texts = []
    for item in data:
        if isinstance(item, str):
            texts.append(item.strip())
        elif isinstance(item, dict) and item.get("text"):
            texts.append(item["text"].strip())
    return [t for t in texts if t]


def load_labeled():
    if not os.path.exists(LABELED):
        return {"reviews": []}
    with open(LABELED, encoding="utf-8") as f:
        return json.load(f)


def save_labeled(obj):
    with open(LABELED, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "sample_reviews.json")
    texts = load_texts(src)
    labeled = load_labeled()
    done = {r["text"] for r in labeled["reviews"] if "text" in r}

    todo = [t for t in texts if t not in done]
    if not todo:
        print("ทุกข้อความถูกติด label แล้ว ไม่มีอะไรให้ทำต่อ")
        return

    print(f"มี {len(todo)} ข้อความที่ยังไม่ติด label (p=บวก u=กลาง n=ลบ s=ข้าม q=ออก)\n")
    added = 0
    for i, text in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {text}")
        ans = input("  label > ").strip().lower()
        if ans == "q":
            break
        if ans == "s" or ans not in KEYMAP:
            print("  (ข้าม)\n")
            continue
        labeled["reviews"].append({"text": text, "label": KEYMAP[ans]})
        added += 1
        print(f"  -> {KEYMAP[ans]}\n")

    save_labeled(labeled)
    print(f"\nบันทึกแล้ว: เพิ่ม {added} รายการ (รวมทั้งหมด {len(labeled['reviews'])} รายการใน {LABELED})")


if __name__ == "__main__":
    main()
