"""Build a local, de-duplicated queue of real reviews for human sentiment labels.

The output is ignored by git because it can contain reviews collected by the
local operator. No model-generated label is written into the queue.

    python -m eval.build_sentiment_queue --target 300
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sqlite3


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _review_id(text: str) -> str:
    return "sent-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def load_real_reviews(database_path: str) -> list[dict]:
    if not os.path.exists(database_path):
        return []
    uri = "file:" + os.path.abspath(database_path).replace("\\", "/") + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        rows = conn.execute(
            "SELECT id, store_name, analyzed_at, payload FROM analysis ORDER BY id"
        ).fetchall()
    records = []
    for analysis_id, store_name, analyzed_at, payload_text in rows:
        try:
            payload = json.loads(payload_text)
        except (TypeError, json.JSONDecodeError):
            continue
        for review in payload.get("reviews", []):
            text = " ".join((review.get("text") or "").split())
            if not text:
                continue
            records.append({
                "id": _review_id(text),
                "text": text,
                "label": "",
                "source": {
                    "kind": "local_analysis",
                    "analysis_id": analysis_id,
                    "store_name": store_name or "",
                    "analyzed_at": analyzed_at or "",
                },
            })
    return records


def build_queue(records: list[dict], *, target: int, seed: int) -> dict:
    unique = {record["id"]: record for record in records}
    reviews = list(unique.values())
    random.Random(seed).shuffle(reviews)
    reviews = reviews[:max(0, target)]
    return {
        "schema_version": 1,
        "kind": "sentiment_label_queue",
        "meta": {
            "target": target,
            "available": len(unique),
            "selected": len(reviews),
            "seed": seed,
            "notice": "ยังไม่ใช่ gold set ต้องติด label โดยมนุษย์และตรวจความเห็นไม่ตรงกันก่อน",
        },
        "reviews": reviews,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=300)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument(
        "--output",
        default=os.path.join(ROOT, "data", "sentiment_label_queue.json"),
    )
    args = parser.parse_args()
    records = load_real_reviews(os.path.join(ROOT, "insightreview.db"))
    document = build_queue(records, target=args.target, seed=args.seed)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(
        f"สร้างคิว {document['meta']['selected']} จาก {document['meta']['available']} รีวิว "
        f"(เป้าหมาย {document['meta']['target']}): {args.output}"
    )
    print("ไฟล์นี้ยังไม่ใช่ gold set และไม่มี label ที่โมเดลสร้างให้")


if __name__ == "__main__":
    main()
