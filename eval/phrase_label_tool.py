"""Interactive phrase-span annotation tool.

The annotator copies a phrase exactly as it appears in the review, then assigns
aspect and sentiment. Progress is atomically saved after every review.

    python -m eval.phrase_label_tool --annotator annotator_a
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from eval.phrase_schema import (  # noqa: E402
    SCHEMA_VERSION, find_occurrences, load_document, save_document,
)

ASPECT_KEYS = {"f": "food", "s": "service", "a": "ambience"}
SENTIMENT_KEYS = {"p": "positive", "u": "neutral", "n": "negative"}


def _safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip()).strip("_") or "annotator"


def _choose(mapping: dict, prompt: str) -> str:
    while True:
        value = input(prompt).strip().lower()
        if value in mapping:
            return mapping[value]
        print("  ค่าไม่ถูกต้อง:", ", ".join(f"{k}={v}" for k, v in mapping.items()))


def _choose_occurrence(occurrences: list[tuple[int, int]]) -> tuple[int, int]:
    if len(occurrences) == 1:
        return occurrences[0]
    print("  พบวลีซ้ำหลายตำแหน่ง:")
    for i, (start, end) in enumerate(occurrences, 1):
        print(f"    {i}) [{start}:{end}]")
    while True:
        try:
            index = int(input("  เลือกตำแหน่ง > ")) - 1
            return occurrences[index]
        except (ValueError, IndexError):
            print("  กรุณาเลือกหมายเลขที่แสดง")


def _load_or_create(output: str, annotator: str) -> dict:
    if os.path.exists(output):
        with open(output, encoding="utf-8") as f:
            return json.load(f)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "phrase_annotations",
        "meta": {"annotator": annotator, "guideline_version": 1},
        "reviews": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default=os.path.join(ROOT, "data", "phrase_label_queue.json"))
    parser.add_argument("--annotator", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    annotator = _safe_name(args.annotator)
    output = args.output or os.path.join(ROOT, "data", f"phrase_annotations_{annotator}.json")
    queue = load_document(args.queue, require_phrases=False)
    doc = _load_or_create(output, annotator)
    # Validate existing progress before continuing.
    if doc["reviews"]:
        from eval.phrase_schema import validate_document
        validate_document(doc)
    done = {review["id"] for review in doc["reviews"]}
    pending = [review for review in queue["reviews"] if review["id"] not in done]

    print(f"ผู้ติด label: {annotator} | เหลือ {len(pending)} รีวิว")
    print("คัดลอกวลีตามต้นฉบับ; Enter เปล่า=จบรีวิว, s=ข้ามรีวิว, q=บันทึกและออก")
    for index, review in enumerate(pending, 1):
        print(f"\n[{index}/{len(pending)}] {review['text']}")
        phrases, status, quit_after = [], "labeled", False
        while True:
            value = input("  phrase > ").strip()
            if value == "q":
                quit_after = True
                break
            if value == "s" and not phrases:
                status = "skipped"
                break
            if not value:
                break
            occurrences = find_occurrences(review["text"], value)
            if not occurrences:
                print("  ไม่พบข้อความนี้แบบตรงตัวในรีวิว กรุณาคัดลอกจากต้นฉบับ")
                continue
            start, end = _choose_occurrence(occurrences)
            aspect = _choose(ASPECT_KEYS, "  aspect [f=food/s=service/a=ambience] > ")
            sentiment = _choose(SENTIMENT_KEYS, "  sentiment [p=positive/u=neutral/n=negative] > ")
            phrases.append({
                "text": review["text"][start:end],
                "start": start,
                "end": end,
                "aspect": aspect,
                "sentiment": sentiment,
            })
        if quit_after:
            save_document(output, doc)
            print(f"บันทึกแล้ว: {output}")
            return
        doc["reviews"].append({
            "id": review["id"],
            "text": review["text"],
            "status": status,
            "phrases": phrases,
        })
        save_document(output, doc)
    print(f"ติด label ครบคิวแล้ว: {output}")


if __name__ == "__main__":
    main()
