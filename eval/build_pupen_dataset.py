"""Assemble the source-preserving 20/20/20 set from frozen AI annotations.

The selections below were made from review text BEFORE running WangchanBERTa.
Ratings and model predictions are not reference labels. This is an AI-annotated
pilot set awaiting independent human validation, not a human gold standard.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

from core.preprocess import is_thai

ROOT = Path(__file__).resolve().parents[1]
POOL = ROOT / "data" / "pupen_collection"
PLACE_ID = "ChIJ6d7RdwSUAjERrnAUJW-I23Q"
# (collection, zero-based source index, reference label, text-based rationale,
#  annotation confidence). Confidence describes annotation, not model output.
SELECTIONS = [
    ("mostRelevant", 2, "positive", "สรุปว่าอาหารอร่อย คุ้มค่าที่รอ และจะกลับมาซ้ำ", "high"),
    ("mostRelevant", 12, "positive", "ระบุว่าอาหารอร่อยและมีเมนูที่ชอบ", "high"),
    ("mostRelevant", 13, "positive", "ชมความสดและสรุปว่าโดยรวมอร่อย", "high"),
    ("mostRelevant", 20, "positive", "ชมรสชาติและการแนะนำเมนูของพนักงาน", "high"),
    ("mostRelevant", 21, "positive", "ชมอาหาร บรรยากาศ และความคุ้มค่า", "high"),
    ("mostRelevant", 25, "positive", "ชมอาหาร ราคา บรรยากาศ และบริการทุกด้าน", "high"),
    ("mostRelevant", 26, "positive", "ชมคุณภาพอาหารและยอมรับว่าราคาเหมาะกับคุณภาพ", "high"),
    ("mostRelevant", 27, "positive", "ชมความสด รสชาติ ความเร็ว และบริการที่จอดรถ", "high"),
    ("mostRelevant", 28, "positive", "ชมอาหารและระบุว่ายังประทับใจเมื่อกลับมา", "high"),
    ("mostRelevant", 30, "positive", "ชมอาหาร บรรยากาศ บริการ และแนะนำร้าน", "high"),
    ("mostRelevant", 31, "positive", "ชมว่ายังสดและวาฟเฟิลอร่อย", "high"),
    ("mostRelevant", 32, "positive", "ชื่นชมหลายด้านและแนะนำให้มา", "high"),
    ("mostRelevant", 39, "positive", "สรุปว่าคุ้มค่าและจะกลับมา แม้มีข้อติเล็กน้อย", "high"),
    ("mostRelevant", 40, "positive", "ยกให้เป็นร้านโปรดและชมอาหารกับความคุ้มค่า", "high"),
    ("mostRelevant", 64, "positive", "ชมอาหาร เบียร์ และความเร็ว", "high"),
    ("mostRelevant", 68, "positive", "ชมอาหารและระบุว่าประทับใจบริการ", "high"),
    ("mostRelevant", 80, "positive", "ชมรสชาติสม่ำเสมอ บรรยากาศ และการดูแล", "high"),
    ("mostRelevant", 94, "positive", "ชมว่าอร่อย บรรยากาศดี และอาหารเร็ว", "high"),
    ("mostRelevant", 118, "positive", "ชมอาหาร บรรยากาศ ราคา และกลับมาบ่อย", "high"),
    ("mostRelevant", 146, "positive", "ชมอาหาร บริการ และราคาถูก", "high"),
    ("mostRelevant", 107, "neutral", "ประเมินว่าตามมาตรฐาน ใช้ได้ ไม่โดดเด่น โดยไม่ชมติรุนแรง", "medium"),
    ("newest", 140, "neutral", "บันทึกสถานที่ วันที่และอุปกรณ์ถ่ายภาพ ไม่มีการประเมินอารมณ์", "high"),
    ("newest", 399, "neutral", "แจ้งชื่อเมนูและราคาโดยไม่แสดงความพอใจหรือไม่พอใจ", "high"),
    ("newest", 499, "neutral", "บอกความถี่การมานั่ง ไม่มีการชมติ", "high"),
    ("newest", 505, "neutral", "บอกว่าเป็นร้านเก่าแก่และรสชาติกับราคามาตรฐาน", "medium"),
    ("neutral-thammada", 29, "neutral", "บรรยายที่จอดรถ ตำแหน่งร้าน และรสชาติธรรมดาไม่จัด", "medium"),
    ("neutral-thammada", 36, "neutral", "ระบุชัดว่าไม่แย่และไม่ว้าว", "high"),
    ("neutral-thammada", 49, "neutral", "แจ้งว่าคนเยอะแม้วันธรรมดา ไม่มีถ้อยคำชมติ", "high"),
    ("neutral-thammada", 93, "neutral", "ประเมินว่าธรรมดาเหมือนร้านทั่วไป", "high"),
    ("neutral-thammada", 94, "neutral", "ระบุรสชาติธรรมดาและจำนวนคน โดยไม่สรุปพอใจหรือไม่พอใจ", "medium"),
    ("neutral-thammada", 98, "neutral", "ระบุเพียงว่ารสชาติธรรมดา", "high"),
    ("neutral-thammada", 99, "neutral", "ระบุเพียงว่าอาหารธรรมดา", "high"),
    ("neutral-choeichoei", 42, "neutral", "ระบุรสชาติเฉยๆและราคาปกติ", "high"),
    ("neutral-choeichoei", 56, "neutral", "แสดงความรู้สึกเฉยๆต่อรสชาติ ไม่มีคำตำหนิชัดเจน", "medium"),
    ("neutral-choeichoei", 57, "neutral", "แสดงความรู้สึกเฉยๆโดยตรง", "high"),
    ("neutral-klang", 66, "neutral", "รสชาติกลางๆไม่จัด พร้อมข้อมูลจำนวนคนและส่วนลด", "medium"),
    ("neutral-klang", 94, "neutral", "ประเมินว่ารสชาติระดับโอเค กลางๆ และไม่จัด", "medium"),
    ("mostRelevant", 163, "neutral", "บรรยายจานใหญ่ ราคาสูง บริการกลางๆและที่จอดรถ โดยไม่มีขั้วเด่น", "medium"),
    ("neutral-thammada", 96, "neutral", "ประเมินว่าธรรมดาและราคาไม่แพงมาก ไม่มีความชื่นชมหรือตำหนิเด่น", "medium"),
    ("neutral-choeichoei", 35, "neutral", "อาหารพอกินได้ ชมบรรยากาศ แต่สรุปด้านอื่นว่าเฉยๆ", "medium"),
    ("mostRelevant", 19, "negative", "ตำหนิการรอ บริการ และราคาแพงเกินไป แม้ชมความสด", "high"),
    ("mostRelevant", 22, "negative", "ตำหนิความสดและความคุ้มค่า พร้อมลดความคาดหวังเรื่องอาหาร", "medium"),
    ("mostRelevant", 84, "negative", "ตำหนิของไม่สดและคุณภาพไม่เหมาะกับราคาอย่างชัดเจน", "high"),
    ("mostRelevant", 133, "negative", "เล่าประสบการณ์พนักงานปฏิบัติไม่ดีและเรียกร้องให้ปรับปรุง", "high"),
    ("mostRelevant", 165, "negative", "ตำหนิรสชาติและแสดงความตกใจกับราคาหรือชนิดหมู", "high"),
    ("mostRelevant", 306, "negative", "แม้ชมรสชาติ แต่สรุปว่าปริมาณไม่เหมาะกับราคา", "medium"),
    ("mostRelevant", 308, "negative", "ตำหนิอาหารหลักและระบุเมนูที่ไม่ควรสั่ง แม้ชมบริการ", "high"),
    ("mostRelevant", 315, "negative", "ตำหนิขนาด ราคา และทรายในอาหารจนต้องทิ้ง", "high"),
    ("mostRelevant", 391, "negative", "ผิดหวังเรื่องราคา ปริมาณ และระบุว่าจะมาครั้งสุดท้าย", "high"),
    ("mostRelevant", 394, "negative", "พบเส้นผม ผิดหวัง และระบุว่าจะไม่กลับมา", "high"),
    ("mostRelevant", 429, "negative", "ตำหนิบริการที่เพิกเฉยต่อการรับออเดอร์ แม้ชมอาหารและวิว", "high"),
    ("mostRelevant", 539, "negative", "ตำหนิบริการไม่ทั่วถึง การตามอาหาร และราคาสูง", "high"),
    ("mostRelevant", 547, "negative", "ตำหนิอาหารและบริการหลายประเด็นอย่างชัดเจน", "high"),
    ("mostRelevant", 556, "negative", "เน้นว่าแพงเมื่อเทียบปริมาณและคุณภาพ แม้บางเมนูรสดี", "high"),
    ("mostRelevant", 560, "negative", "ไม่พอใจราคาที่สูงขึ้นและปริมาณที่ลดลง", "high"),
    ("mostRelevant", 566, "negative", "ตำหนิรสชาติและการคิดค่ามะนาวโดยไม่แจ้ง", "high"),
    ("mostRelevant", 579, "negative", "ไม่พอใจการรอและการไม่แจ้งว่าอาหารไม่ได้ แม้ชมรสชาติ", "high"),
    ("mostRelevant", 594, "negative", "ตำหนิการรอ ความช้า และราคาแพง", "high"),
    ("newest", 191, "negative", "ตำหนิคุณภาพที่ลดลงแม้ขึ้นราคาแล้ว", "high"),
    ("newest", 386, "negative", "ตำหนิพนักงานไม่สนใจและแนะนำให้ไปร้านอื่น", "high"),
]


def main():
    target = ROOT / "data" / "labeled_reviews.json"
    provenance_path = target.with_suffix(".provenance.json")
    existing = json.loads(target.read_text(encoding="utf-8"))
    if provenance_path.exists():
        existing = json.loads(provenance_path.read_text(encoding="utf-8"))
    created_at = (existing.get("meta", {}).get("created_at")
                  if existing.get("kind") == "real_review_sentiment_ai_annotated_pilot" else None)
    documents = {path.name.removesuffix("_reviews.json"): json.loads(path.read_text(encoding="utf-8"))
                 for path in sorted(POOL.glob("*_reviews.json"))}
    rows = []
    for tag, index, label, rationale, confidence in SELECTIONS:
        document = documents[tag]
        raw = document["reviews"][index]
        text = raw["text"]
        assert raw.get("originalLanguage") == "th" and is_thai(text, threshold=0.5), (tag, index)
        assert raw.get("placeId") == PLACE_ID and raw.get("reviewOrigin") == "Google"
        assert raw.get("reviewId") and raw.get("publishedAtDate")
        rows.append({
            "id": "pupen-" + hashlib.sha256(raw["reviewId"].encode()).hexdigest()[:16],
            "text": text, "label": label,
            "annotation": {"annotator": "Codex AI", "method": "text-based AI annotation before model evaluation",
                           "rationale": rationale, "confidence": confidence, "human_validated": False},
            "source": {"platform": "Google Maps", "store_name": raw["title"],
                       "place_id": raw["placeId"], "cid": raw["cid"], "place_url": raw["url"],
                       "review_id": raw["reviewId"], "review_url": raw.get("reviewUrl"),
                       "published_at": raw["publishedAtDate"], "collected_at": raw.get("scrapedAt"),
                       "original_language": raw["originalLanguage"], "stars": raw.get("stars"),
                       "collection_file": f"data/pupen_collection/{tag}_reviews.json",
                       "source_index": index, "apify_run_id": document["collection"]["run_id"],
                       "apify_dataset_id": document["collection"]["dataset_id"],
                       "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()},
        })
    assert Counter(row["label"] for row in rows) == {"positive": 20, "neutral": 20, "negative": 20}
    assert len({row["id"] for row in rows}) == len({" ".join(row["text"].split()) for row in rows}) == 60
    archive = ROOT / "data" / "evaluation_archive" / "2026-09-29-original"
    archive.mkdir(parents=True, exist_ok=True)
    for relative in ("data/labeled_reviews.json", "eval/report.txt", "eval/confusion_matrix.csv", "eval/confusion_matrix.png"):
        source = ROOT / relative
        destination = archive / source.name
        if not destination.exists():
            shutil.copy2(source, destination)
    all_records = [item for document in documents.values() for item in document["reviews"]]
    unique = {item["reviewId"]: item for item in all_records if item.get("reviewId")}
    thai = {key: item for key, item in unique.items() if item.get("originalLanguage") == "th"
            and is_thai(item.get("text") or "", threshold=0.5)}
    output = {
        "schema_version": 2,
        "kind": "real_review_sentiment_ai_annotated_pilot",
        "_comment": "รีวิวจริงจาก Google Maps ของ Pupen Seafood; ป้ายกำกับโดย AI ก่อนรันโมเดล ยังไม่ผ่านผู้ประเมินมนุษย์อิสระ",
        "meta": {
            "dataset_name": "Pupen Seafood: 60 real Thai Google Maps reviews, AI-annotated pilot (20/20/20)",
            "created_at": created_at or datetime.now(timezone.utc).isoformat(), "store_name": "Pupen Seafood (ร้านอาหารปูเป็น ซีฟู้ด)",
            "place_id": PLACE_ID, "class_counts": dict(Counter(row["label"] for row in rows)),
            "annotation": {"method": "AI text-based labels frozen before WangchanBERTa inference; not star-derived",
                           "annotator": "Codex AI", "human_validation": "pending; no independent human annotators",
                           "inter_annotator_agreement": None,
                           "rules": {"positive": "ความพึงพอใจหรือการชื่นชมเป็นใจความหลัก",
                                     "negative": "ความไม่พึงพอใจหรือคำตำหนิเป็นใจความหลัก แม้มีคำชมประกอบ",
                                     "neutral": "ข้อเท็จจริง ความรู้สึกเฉยๆ หรือการประเมินระดับปานกลางที่ไม่มีขั้วเด่น; การมีทั้งชมและติไม่ทำให้เป็นกลางอัตโนมัติ"}},
            "sampling": {"method": "purposive balanced quota selection by review text, not a random sample",
                         "source_sorts": ["mostRelevant", "newest"],
                         "additional_keyword_searches": ["เฉย", "ธรรมดา", "กลางๆ", "เฉยๆ"],
                         "returned_records": len(all_records), "unique_review_ids": len(unique),
                         "unique_nonempty_original_thai_reviews": len(thai),
                         "text_policy": "whole original text copied exactly; no translation, paraphrase or sentence extraction",
                         "selection_policy": "read candidate texts, prioritize interpretable short-to-medium whole reviews; exclude strongly mixed or ambiguous polarity",
                         "cost_usd": round(sum(d["collection"].get("usageTotalUsd") or 0 for d in documents.values()), 6)},
            "limitations": ["Single restaurant and only 60 purposively selected reviews",
                            "Artificially balanced labels do not estimate natural class frequencies",
                            "Keyword searches and preference for interpretable reviews introduce selection bias",
                            "AI labels require independent human validation; not a human gold standard",
                            "Neutral includes middling/indifferent assessments; boundary judgments may vary"],
            "previous_dataset_archive": str(archive.relative_to(ROOT)).replace("\\", "/"),
        },
        "reviews": rows,
    }
    # Keep the working dataset as readable as the original text/label format.
    simple_rows = [{"text": row["text"], "label": row["label"]} for row in rows]
    dataset_text = '{\n  "reviews": [\n' + ",\n".join(
        "    " + json.dumps(row, ensure_ascii=False) for row in simple_rows
    ) + "\n  ]\n}\n"
    output["dataset_file"] = "data/labeled_reviews.json"
    output["dataset_sha256"] = hashlib.sha256(dataset_text.encode("utf-8")).hexdigest()
    provenance_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    target.write_bytes(dataset_text.encode("utf-8"))
    print(json.dumps({"path": str(target), "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                      "counts": output["meta"]["class_counts"], "sampling": output["meta"]["sampling"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
