"""Research evaluation must never report fallback output as model output."""
import unittest
from unittest import mock

from eval import evaluate


class StrictEvaluationTests(unittest.TestCase):
    def test_inference_failure_propagates_without_fallback(self):
        with mock.patch.object(evaluate.sentiment, "_predict_model", side_effect=RuntimeError("model failed")), \
             mock.patch.object(evaluate.sentiment, "predict") as fallback:
            with self.assertRaisesRegex(RuntimeError, "model failed"):
                evaluate.predict_all([{"text": "อาหารอร่อย", "label": "positive"}], True, strict_model=True)
            fallback.assert_not_called()

    def test_metrics_match_hand_calculated_example(self):
        truth = ["positive", "positive", "neutral", "neutral", "negative", "negative"]
        predictions = ["positive", "negative", "positive", "neutral", "negative", "negative"]
        cm = evaluate.confusion_matrix(truth, predictions)
        metrics = evaluate.per_class_metrics(cm)
        self.assertAlmostEqual(metrics["positive"]["precision"], 0.5)
        self.assertAlmostEqual(metrics["neutral"]["recall"], 0.5)
        self.assertAlmostEqual(metrics["negative"]["f1"], 0.8)
        self.assertAlmostEqual(evaluate.cohen_kappa(truth, predictions), 0.5)


if __name__ == "__main__":
    unittest.main()
