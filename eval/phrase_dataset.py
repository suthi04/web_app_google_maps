"""Phrase-gold statistics and deterministic train/dev/test splitting."""
from __future__ import annotations

import argparse
import json
import os
import random
import statistics

from eval.phrase_schema import ASPECTS, SENTIMENTS, load_document, save_document


def dataset_stats(doc: dict) -> dict:
    reviews = doc.get("reviews", [])
    usable = [r for r in reviews if r.get("status") != "skipped"]
    phrases = [p for review in usable for p in review.get("phrases", [])]
    lengths = [p["end"] - p["start"] for p in phrases]
    aspect_counts = {label: 0 for label in ASPECTS}
    sentiment_counts = {label: 0 for label in SENTIMENTS}
    joint_counts = {}
    for phrase in phrases:
        aspect_counts[phrase["aspect"]] += 1
        sentiment_counts[phrase["sentiment"]] += 1
        key = f"{phrase['aspect']}:{phrase['sentiment']}"
        joint_counts[key] = joint_counts.get(key, 0) + 1
    return {
        "reviews_total": len(reviews),
        "reviews_usable": len(usable),
        "reviews_skipped": len(reviews) - len(usable),
        "reviews_with_phrases": sum(bool(r.get("phrases")) for r in usable),
        "reviews_without_phrases": sum(not r.get("phrases") for r in usable),
        "phrases_total": len(phrases),
        "phrases_per_review_mean": len(phrases) / len(usable) if usable else 0.0,
        "phrase_length_mean": statistics.fmean(lengths) if lengths else 0.0,
        "phrase_length_median": statistics.median(lengths) if lengths else 0.0,
        "aspect_counts": aspect_counts,
        "sentiment_counts": sentiment_counts,
        "joint_counts": dict(sorted(joint_counts.items())),
    }


def split_document(
    doc: dict,
    *,
    train_ratio: float = 0.70,
    dev_ratio: float = 0.15,
    seed: int = 2026,
) -> dict[str, dict]:
    test_ratio = 1.0 - train_ratio - dev_ratio
    if train_ratio <= 0 or dev_ratio < 0 or test_ratio <= 0:
        raise ValueError("ratios must satisfy train>0, dev>=0, test>0 and sum to 1")

    reviews = [r for r in doc.get("reviews", []) if r.get("status") != "skipped"]
    random.Random(seed).shuffle(reviews)
    n = len(reviews)
    train_end = int(n * train_ratio)
    dev_end = train_end + int(n * dev_ratio)
    groups = {
        "train": reviews[:train_end],
        "dev": reviews[train_end:dev_end],
        "test": reviews[dev_end:],
    }
    result = {}
    for name, items in groups.items():
        result[name] = {
            "schema_version": doc["schema_version"],
            "kind": "phrase_gold_split",
            "meta": {
                "split": name,
                "seed": seed,
                "train_ratio": train_ratio,
                "dev_ratio": dev_ratio,
                "test_ratio": test_ratio,
                "source_kind": doc.get("kind", "phrase_gold"),
            },
            "reviews": items,
        }
    return result


def assert_no_leakage(splits: dict[str, dict]) -> None:
    seen = {}
    for name, doc in splits.items():
        for review in doc["reviews"]:
            rid = review["id"]
            if rid in seen:
                raise ValueError(f"review {rid} appears in both {seen[rid]} and {name}")
            seen[rid] = name


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("gold")
    parser.add_argument("--split-dir")
    parser.add_argument("--train-ratio", type=float, default=0.70)
    parser.add_argument("--dev-ratio", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()

    gold = load_document(args.gold)
    print(json.dumps(dataset_stats(gold), ensure_ascii=False, indent=2))
    if args.split_dir:
        splits = split_document(
            gold,
            train_ratio=args.train_ratio,
            dev_ratio=args.dev_ratio,
            seed=args.seed,
        )
        assert_no_leakage(splits)
        os.makedirs(args.split_dir, exist_ok=True)
        for name, doc in splits.items():
            path = os.path.join(args.split_dir, f"{name}.json")
            save_document(path, doc)
            print(f"{name}: {len(doc['reviews'])} reviews -> {path}")


if __name__ == "__main__":
    main()
