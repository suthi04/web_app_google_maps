"""Compare the rule-based and Gemini (LLM) extraction engines on the same reviews.

Rule-based always runs (offline). The LLM half runs only with run_llm=True AND a
configured GEMINI_API_KEY; otherwise it is reported as skipped. This is the
evidence for the rule-vs-LLM comparison in the write-up.

CLI:  python -m scripts.compare_engines [--llm]
      (uses data/labeled_reviews.json when present, else the demo sample)
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from core import preprocess, sentiment, aspect
from core.phrases import llm_extract
from core import pipeline


def _summarize(contract: dict) -> dict:
    per_aspect, total = {}, 0
    for a, by_sent in contract.items():
        words = []
        for items in by_sent.values():
            words += [it["word"] for it in items]
        per_aspect[a] = words
        total += len(words)
    return {"total_phrases": total, "per_aspect": per_aspect}


def _run_rule(reviews: list) -> dict:
    prepared = preprocess.filter_and_prepare(reviews)
    prepared = sentiment.analyze_all(prepared)
    prepared = aspect.tag_aspects(prepared)
    return _summarize(pipeline._rule_phrase_pipeline(prepared))


def compare(reviews: list, run_llm: bool = False) -> dict:
    report = {"rule": _run_rule(reviews), "llm": None}
    if run_llm and llm_extract.available():
        try:
            report["llm"] = _summarize(llm_extract.extract_all(reviews))
        except Exception as e:
            report["llm"] = {"error": str(e)}
    return report


def _load_reviews() -> list:
    path = os.path.join(config.DATA_DIR, "labeled_reviews.json")
    if not os.path.exists(path):
        path = os.path.join(config.DATA_DIR, "sample_reviews.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["reviews"] if isinstance(data, dict) else data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true", help="also run the Gemini engine")
    args = ap.parse_args()
    report = compare(_load_reviews(), run_llm=args.llm)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
