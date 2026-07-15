"""Adjudicate two independent annotation files into the final phrase gold set.

Identical reviews are accepted automatically. Conflicts can choose A, B, their
union, no phrase, or an explicit subset of the displayed candidates.
"""
from __future__ import annotations

import argparse
import os

from eval.phrase_schema import SCHEMA_VERSION, load_document, save_document

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _key(phrase: dict) -> tuple:
    return (phrase["start"], phrase["end"], phrase["aspect"], phrase["sentiment"])


def unique_phrases(*groups: list[dict]) -> list[dict]:
    out = {}
    for group in groups:
        for phrase in group:
            out.setdefault(_key(phrase), phrase)
    return [out[key] for key in sorted(out)]


def _show(label: str, phrases: list[dict]) -> None:
    print(f"  {label}:")
    if not phrases:
        print("    (ไม่มีวลี)")
    for phrase in phrases:
        print(
            f"    [{phrase['start']}:{phrase['end']}] {phrase['text']!r} "
            f"| {phrase['aspect']} | {phrase['sentiment']}"
        )


def _resolve(text: str, a: list[dict], b: list[dict]) -> list[dict] | None:
    candidates = unique_phrases(a, b)
    print("\n", text)
    _show("Annotator A", a); _show("Annotator B", b)
    print("  Candidate union:")
    for index, phrase in enumerate(candidates, 1):
        print(
            f"    {index}) [{phrase['start']}:{phrase['end']}] {phrase['text']!r} "
            f"| {phrase['aspect']} | {phrase['sentiment']}"
        )
    while True:
        value = input("  เลือก a / b / m=union / 0=ไม่มี / 1,3=subset / q=ออก > ").strip().lower()
        if value == "a": return list(a)
        if value == "b": return list(b)
        if value == "m": return candidates
        if value == "0": return []
        if value == "q": return None
        try:
            indices = [int(x.strip()) - 1 for x in value.split(",")]
            if indices and all(0 <= i < len(candidates) for i in indices):
                return [candidates[i] for i in sorted(set(indices))]
        except ValueError:
            pass
        print("  คำสั่งไม่ถูกต้อง")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("annotation_a")
    parser.add_argument("annotation_b")
    parser.add_argument("--output", default=os.path.join(ROOT, "data", "phrase_gold.json"))
    args = parser.parse_args()

    doc_a, doc_b = load_document(args.annotation_a), load_document(args.annotation_b)
    by_b = {review["id"]: review for review in doc_b["reviews"]
            if review.get("status") != "skipped"}
    shared = [review for review in doc_a["reviews"]
              if review.get("status") != "skipped" and review["id"] in by_b]
    if not shared:
        raise SystemExit("annotation files ไม่มี review id ร่วมกัน")

    if os.path.exists(args.output):
        gold = load_document(args.output)
    else:
        gold = {
            "schema_version": SCHEMA_VERSION,
            "kind": "phrase_gold",
            "meta": {
                "guideline_version": 1,
                "annotator_a": doc_a.get("meta", {}).get("annotator", "A"),
                "annotator_b": doc_b.get("meta", {}).get("annotator", "B"),
            },
            "reviews": [],
        }
    done = {review["id"] for review in gold["reviews"]}
    auto = conflicts = 0
    for ra in shared:
        if ra["id"] in done:
            continue
        rb = by_b[ra["id"]]
        pa, pb = ra.get("phrases", []), rb.get("phrases", [])
        if {_key(x) for x in pa} == {_key(x) for x in pb}:
            chosen = unique_phrases(pa)
            auto += 1
        else:
            conflicts += 1
            chosen = _resolve(ra["text"], pa, pb)
            if chosen is None:
                save_document(args.output, gold)
                print(f"บันทึกแล้ว: {args.output}")
                return
        gold["reviews"].append({
            "id": ra["id"], "text": ra["text"], "phrases": chosen,
        })
        save_document(args.output, gold)
    print(
        f"adjudicate ครบ {len(gold['reviews'])} รีวิว "
        f"(auto={auto}, conflicts={conflicts}): {args.output}"
    )


if __name__ == "__main__":
    main()
