"""Detailed phrase errors for qualitative analysis in the thesis."""
from __future__ import annotations

import argparse
import json
import os

from eval.phrase_evaluate import predict_dataset
from eval.phrase_metrics import match_phrases
from eval.phrase_schema import load_document

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def analyze_errors(gold: dict, predicted_by_id: dict, threshold: float = 0.5) -> dict:
    cases = []
    summary = {
        "reviews": len(gold["reviews"]),
        "false_negatives": 0,
        "false_positives": 0,
        "boundary_errors": 0,
        "aspect_errors": 0,
        "sentiment_errors": 0,
        "joint_label_errors": 0,
    }
    for review in gold["reviews"]:
        truth = review.get("phrases", [])
        predicted = predicted_by_id.get(review["id"], [])
        matches = match_phrases(truth, predicted, partial=True, threshold=threshold)
        matched_truth = {gi for gi, _, _ in matches}
        matched_pred = {pi for _, pi, _ in matches}
        errors = []
        for gi, pi, iou in matches:
            g, p = truth[gi], predicted[pi]
            kinds = []
            if g["start"] != p["start"] or g["end"] != p["end"]:
                kinds.append("boundary"); summary["boundary_errors"] += 1
            if g["aspect"] != p["aspect"]:
                kinds.append("aspect"); summary["aspect_errors"] += 1
            if g["sentiment"] != p["sentiment"]:
                kinds.append("sentiment"); summary["sentiment_errors"] += 1
            if g["aspect"] != p["aspect"] or g["sentiment"] != p["sentiment"]:
                summary["joint_label_errors"] += 1
            if kinds:
                errors.append({
                    "types": kinds,
                    "iou": iou,
                    "gold": g,
                    "predicted": p,
                })
        for gi, phrase in enumerate(truth):
            if gi not in matched_truth:
                summary["false_negatives"] += 1
                errors.append({"types": ["false_negative"], "gold": phrase})
        for pi, phrase in enumerate(predicted):
            if pi not in matched_pred:
                summary["false_positives"] += 1
                errors.append({"types": ["false_positive"], "predicted": phrase})
        if errors:
            cases.append({
                "id": review["id"],
                "text": review["text"],
                "errors": errors,
            })
    summary["reviews_with_errors"] = len(cases)
    return {"summary": summary, "cases": cases}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("gold")
    parser.add_argument("--engine", choices=("rule", "llm"), default="rule")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--llm-batch-size", type=int, default=25)
    parser.add_argument(
        "--output", default=os.path.join(ROOT, "eval", "phrase_errors.json")
    )
    args = parser.parse_args()
    if not 0 < args.threshold <= 1:
        parser.error("--threshold must be in (0, 1]")
    gold = load_document(args.gold)
    predictions = predict_dataset(
        gold["reviews"], engine=args.engine, llm_batch_size=args.llm_batch_size
    )
    report = analyze_errors(gold, predictions, args.threshold)
    report["engine"] = args.engine
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2); f.write("\n")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print("รายละเอียด:", args.output)


if __name__ == "__main__":
    main()
