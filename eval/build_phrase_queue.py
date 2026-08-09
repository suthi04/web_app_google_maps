"""Build a deterministic, de-duplicated phrase-annotation queue from local data.

Uses the existing SQLite analyses plus the two repository fixtures by default. It
does not call Apify/Gemini and writes a local-only file ignored by git.

    python -m eval.build_phrase_queue
    python -m eval.build_phrase_queue --limit 100 --seed 2026
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from eval.phrase_schema import SCHEMA_VERSION, review_id, save_document  # noqa: E402


def _from_database(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    uri = "file:" + os.path.abspath(path).replace("\\", "/") + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        rows = conn.execute("SELECT id, store_name, payload FROM analysis ORDER BY id").fetchall()
    out = []
    for analysis_id, store_name, payload_text in rows:
        try:
            payload = json.loads(payload_text)
        except (TypeError, json.JSONDecodeError):
            continue
        for review in payload.get("reviews", []):
            text = (review.get("text") or "").strip()
            if text:
                out.append({
                    "text": text,
                    "source": {
                        "kind": "analysis",
                        "analysis_id": analysis_id,
                        "store_name": store_name or "",
                    },
                })
    return out


def _from_json(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    reviews = data.get("reviews", []) if isinstance(data, dict) else data
    out = []
    for review in reviews:
        text = review if isinstance(review, str) else review.get("text", "")
        text = (text or "").strip()
        if text:
            out.append({
                "text": text,
                "source": {"kind": "fixture", "file": os.path.basename(path)},
            })
    return out


def build_queue(records: list[dict], *, seed: int = 2026, limit: int | None = None) -> dict:
    unique = {}
    for record in records:
        text = " ".join((record.get("text") or "").split())
        if not text:
            continue
        rid = review_id(text)
        unique.setdefault(rid, {
            "id": rid,
            "text": text,
            "source": record.get("source", {"kind": "unknown"}),
        })
    reviews = list(unique.values())
    random.Random(seed).shuffle(reviews)
    if limit is not None:
        reviews = reviews[:max(0, limit)]
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "phrase_label_queue",
        "meta": {
            "seed": seed,
            "available_before_limit": len(unique),
            "total": len(reviews),
        },
        "reviews": reviews,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=os.path.join(ROOT, "data", "phrase_label_queue.json"))
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--no-db", action="store_true")
    parser.add_argument("--no-fixtures", action="store_true")
    args = parser.parse_args()

    records = []
    if not args.no_db:
        records.extend(_from_database(os.path.join(ROOT, "insightreview.db")))
    if not args.no_fixtures:
        records.extend(_from_json(os.path.join(ROOT, "data", "sample_reviews.json")))
        records.extend(_from_json(os.path.join(ROOT, "data", "labeled_reviews.json")))
    doc = build_queue(records, seed=args.seed, limit=args.limit)
    save_document(args.output, doc, require_phrases=False)
    print(f"สร้างคิวแล้ว {len(doc['reviews'])} รีวิว: {args.output}")
    print("ไฟล์นี้ยังไม่ใช่ gold set — ต้องติด label อย่างน้อย 2 คนแล้ว adjudicate ก่อน")


if __name__ == "__main__":
    main()
