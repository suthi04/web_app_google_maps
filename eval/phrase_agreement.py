"""Measure inter-annotator phrase agreement (span F1 + aspect/sentiment kappa)."""
from __future__ import annotations

import argparse
import json

from eval.phrase_metrics import agreement_report
from eval.phrase_schema import load_document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("annotation_a")
    parser.add_argument("annotation_b")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--output")
    args = parser.parse_args()
    if not 0 < args.threshold <= 1:
        parser.error("--threshold must be in (0, 1]")
    doc_a = load_document(args.annotation_a)
    doc_b = load_document(args.annotation_b)
    report = agreement_report(doc_a, doc_b, args.threshold)
    output = json.dumps(report, ensure_ascii=False, indent=2)
    print(output)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output + "\n")


if __name__ == "__main__":
    main()
