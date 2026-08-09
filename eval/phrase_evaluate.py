"""Evaluate the offline rule phrase engine against an adjudicated gold file."""
from __future__ import annotations

import argparse
import json
import os
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core import aspect, pipeline, preprocess, sentiment  # noqa: E402
from core.phrases import llm_extract  # noqa: E402
from eval.phrase_metrics import evaluate_reviews  # noqa: E402
from eval.phrase_schema import load_document  # noqa: E402


def _normal_with_map(text: str) -> tuple[str, list[int]]:
    chars, positions = [], []
    for index, char in enumerate(text):
        # Match through whitespace, punctuation and emoji removed by preprocessing,
        # while preserving Thai combining marks (Unicode category M).
        if char.isspace() or unicodedata.category(char)[0] in {"P", "S", "Z"}:
            continue
        chars.append(char.lower())
        positions.append(index)
    return "".join(chars), positions


def locate_phrase(text: str, candidates: list[str], used: set[tuple[int, int]]) -> tuple[int, int]:
    normalized, positions = _normal_with_map(text)
    for candidate in candidates:
        needle, _ = _normal_with_map(candidate or "")
        if not needle:
            continue
        offset = 0
        while True:
            pos = normalized.find(needle, offset)
            if pos < 0:
                break
            span = (positions[pos], positions[pos + len(needle) - 1] + 1)
            if span not in used:
                return span
            offset = pos + 1
    return -1, -1


def predict_rule(text: str) -> list[dict]:
    prepared = preprocess.filter_and_prepare([{"text": text}])
    if not prepared:
        return []
    sentiment.analyze_all(prepared, use_model=False)
    aspect.tag_aspects(prepared)
    phrases = pipeline.rule_phrase_occurrences(prepared)

    used, out, seen = set(), [], set()
    for phrase in phrases:
        start, end = locate_phrase(
            text,
            [phrase.surface, phrase.display, phrase.canonical, phrase.label],
            used,
        )
        if start >= 0:
            used.add((start, end))
            shown = text[start:end]
        else:
            shown = phrase.display or phrase.surface or phrase.canonical
        item = {
            "text": shown,
            "start": start,
            "end": end,
            "aspect": phrase.aspect,
            "sentiment": phrase.sentiment,
        }
        key = (start, end, item["aspect"], item["sentiment"], shown)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def predictions_from_llm_payload(reviews: list[dict], payload: dict) -> dict:
    """Map indexed Gemini occurrences back to exact source spans when possible."""
    result = {review["id"]: [] for review in reviews}
    used = {review["id"]: set() for review in reviews}
    seen = {review["id"]: set() for review in reviews}
    for occurrence in llm_extract.payload_occurrences(payload):
        index = occurrence["index"]
        if index >= len(reviews):
            continue
        review = reviews[index]
        rid, text = review["id"], review["text"]
        start, end = locate_phrase(text, [occurrence["text"]], used[rid])
        if start >= 0:
            used[rid].add((start, end))
            shown = text[start:end]
        else:
            shown = occurrence["text"]
        item = {
            "text": shown,
            "start": start,
            "end": end,
            "aspect": occurrence["aspect"],
            "sentiment": occurrence["sentiment"],
        }
        key = (start, end, item["aspect"], item["sentiment"], shown)
        if key not in seen[rid]:
            seen[rid].add(key)
            result[rid].append(item)
    return result


def predict_dataset(
    reviews: list[dict], *, engine: str = "rule", llm_batch_size: int = 25
) -> dict:
    if engine == "rule":
        return {review["id"]: predict_rule(review["text"]) for review in reviews}
    if engine != "llm":
        raise ValueError(f"unknown engine {engine!r}")
    if llm_batch_size <= 0:
        raise ValueError("llm_batch_size must be positive")
    if not llm_extract.available():
        raise RuntimeError("Gemini evaluation requires GEMINI_API_KEY and google-genai")

    predictions = {review["id"]: [] for review in reviews}
    for start in range(0, len(reviews), llm_batch_size):
        chunk = reviews[start:start + llm_batch_size]
        payload = llm_extract.extract_payload([{"text": r["text"]} for r in chunk])
        predictions.update(predictions_from_llm_payload(chunk, payload))
    return predictions


def build_report(
    gold: dict,
    threshold: float = 0.5,
    *,
    engine: str = "rule",
    llm_batch_size: int = 25,
) -> dict:
    predictions = predict_dataset(
        gold["reviews"], engine=engine, llm_batch_size=llm_batch_size
    )
    report = evaluate_reviews(gold["reviews"], predictions, threshold)
    report["engine"] = engine
    report["schema_version"] = gold["schema_version"]
    report["unaligned_predictions"] = sum(
        item["start"] < 0 for items in predictions.values() for item in items
    )
    return report


def _format(report: dict) -> str:
    lines = [
        "InsightReview — Phrase-level Evaluation",
        f"reviews={report['reviews']} gold={report['gold_phrases']} "
        f"predicted={report['predicted_phrases']}",
        f"partial IoU threshold={report['partial_iou_threshold']}",
    ]
    for key in ("exact", "partial", "partial_aspect", "partial_sentiment", "partial_joint"):
        value = report[key]
        lines.append(
            f"{key:<20} P={value['precision']:.4f} R={value['recall']:.4f} "
            f"F1={value['f1']:.4f} (TP={value['tp']} FP={value['fp']} FN={value['fn']})"
        )
    aspect_m = report["aspect_on_partial_matches"]
    sent_m = report["sentiment_on_partial_matches"]
    lines.append(f"aspect matched-only   accuracy={aspect_m['accuracy']:.4f} macro-F1={aspect_m['macro_f1']:.4f}")
    lines.append(f"sentiment matched-only accuracy={sent_m['accuracy']:.4f} macro-F1={sent_m['macro_f1']:.4f}")
    lines.append(f"unaligned predictions={report['unaligned_predictions']}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("gold", help="adjudicated phrase gold JSON")
    parser.add_argument("--engine", choices=("rule", "llm"), default="rule")
    parser.add_argument("--llm-batch-size", type=int, default=25)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--json-output", default=os.path.join(ROOT, "eval", "phrase_report.json"))
    parser.add_argument("--text-output", default=os.path.join(ROOT, "eval", "phrase_report.txt"))
    args = parser.parse_args()
    if not 0 < args.threshold <= 1:
        parser.error("--threshold must be in (0, 1]")

    gold = load_document(args.gold)
    report = build_report(
        gold,
        args.threshold,
        engine=args.engine,
        llm_batch_size=args.llm_batch_size,
    )
    with open(args.json_output, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2); f.write("\n")
    text = _format(report)
    with open(args.text_output, "w", encoding="utf-8") as f:
        f.write(text)
    print(text, end="")


if __name__ == "__main__":
    main()
