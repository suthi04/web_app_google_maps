"""Evaluate slang, factual-neutral, mixed, and negation edge cases separately.

This curated challenge set is diagnostic only. It must never be merged into or
reported as the independently labelled gold-standard score.
"""
import argparse
import os

import evaluate


CHALLENGE_PATH = os.path.join(
    evaluate.ROOT, "data", "sentiment_challenge_reviews.json"
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--engine",
        choices=("current", "model", "rule"),
        default="current",
        help="current=ค่าที่ตั้งไว้ในระบบ, model=WangchanBERTa, rule=พจนานุกรม",
    )
    args = parser.parse_args()
    use_model = {"current": None, "model": True, "rule": False}[args.engine]
    items = evaluate.load_dataset(CHALLENGE_PATH)
    if not items:
        raise SystemExit("ไม่พบข้อมูลใน sentiment challenge set")
    y_true, y_pred = evaluate.predict_all(items, use_model=use_model)
    report_text, cm = evaluate.build_report(
        items,
        y_true,
        y_pred,
        title="  InsightReview — รายงานชุดท้าทายภาษาใช้งานจริง",
        dataset_label="curated challenge (ไม่รวมในคะแนน gold standard)",
        engine_label=evaluate.sentiment.engine_name(use_model=use_model),
    )
    print(report_text)
    prefix = "challenge_" if args.engine == "current" else f"challenge_{args.engine}_"
    has_png = evaluate.save_outputs(report_text, cm, prefix=prefix)
    outputs = f"eval/{prefix}report.txt, eval/{prefix}confusion_matrix.csv"
    if has_png:
        outputs += f", eval/{prefix}confusion_matrix.png"
    print(f"\nบันทึกแล้ว: {outputs}")


if __name__ == "__main__":
    main()
