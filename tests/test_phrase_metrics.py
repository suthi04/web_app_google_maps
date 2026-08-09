import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval import phrase_metrics, phrase_schema


def _phrase(start, end, aspect="food", sentiment="positive"):
    return {"start": start, "end": end, "aspect": aspect, "sentiment": sentiment}


class TestPhraseMetrics(unittest.TestCase):
    def test_span_iou(self):
        self.assertAlmostEqual(
            phrase_metrics.span_iou(_phrase(0, 10), _phrase(5, 15)),
            5 / 15,
        )

    def test_exact_and_partial_are_distinct(self):
        gold = [_phrase(0, 10)]
        pred = [_phrase(2, 10)]
        exact, _ = phrase_metrics.detection_metrics(gold, pred, partial=False)
        partial, _ = phrase_metrics.detection_metrics(
            gold, pred, partial=True, threshold=0.5
        )
        self.assertEqual(exact["tp"], 0)
        self.assertEqual(partial["tp"], 1)

    def test_label_requirement_is_end_to_end(self):
        gold = [_phrase(0, 10, aspect="food")]
        pred = [_phrase(0, 10, aspect="service")]
        metrics, _ = phrase_metrics.detection_metrics(
            gold, pred, partial=True, require_fields=("aspect",)
        )
        self.assertEqual(metrics["tp"], 0)
        self.assertEqual(metrics["fp"], 1)
        self.assertEqual(metrics["fn"], 1)

    def test_evaluate_reviews_reports_joint_metrics(self):
        text = "อาหารอร่อย"
        rid = phrase_schema.review_id(text)
        gold = [{"id": rid, "text": text, "phrases": [_phrase(0, 10)]}]
        report = phrase_metrics.evaluate_reviews(gold, {rid: [_phrase(0, 10)]})
        self.assertEqual(report["exact"]["f1"], 1.0)
        self.assertEqual(report["partial_joint"]["f1"], 1.0)

    def test_cohen_kappa_perfect(self):
        labels = ("positive", "neutral", "negative")
        self.assertEqual(
            phrase_metrics.cohen_kappa(
                ["positive", "neutral"], ["positive", "neutral"], labels
            ),
            1.0,
        )

    def test_agreement_report(self):
        text = "อาหารอร่อย"
        rid = phrase_schema.review_id(text)
        review = {"id": rid, "text": text, "phrases": [_phrase(0, 10)]}
        doc = {"schema_version": 1, "reviews": [review]}
        report = phrase_metrics.agreement_report(doc, doc)
        self.assertEqual(report["partial"]["f1"], 1.0)
        self.assertEqual(report["aspect_kappa"], 1.0)

        skipped = {"schema_version": 1, "reviews": [dict(review, status="skipped")]}
        skipped_report = phrase_metrics.agreement_report(skipped, doc)
        self.assertEqual(skipped_report["shared_reviews"], 0)


if __name__ == "__main__":
    unittest.main()
