"""โหมดโมเดล: เมื่อโมเดลล้มเหลวแล้ว (_model_status == "failed") ต้อง "ไม่" พยายาม
โหลด/เรียกโมเดลซ้ำทุกข้อความ (กันการวิเคราะห์ลากยาวหลายนาทีใน failure mode),
ต้องส่ง truncation=True กัน token เกิน, และ analyze_all ต้อง batch เป็น call เดียว"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from core import sentiment
from core.phrases.model import Phrase


class TestFailedModelGuard(unittest.TestCase):
    def test_predict_does_not_retry_failed_model(self):
        with mock.patch.object(config, "get_use_model", return_value=True), \
             mock.patch.object(sentiment, "_model_status", "failed"), \
             mock.patch.object(sentiment, "_predict_model") as predict_model:
            out = sentiment.predict({"clean": "อาหารอร่อย", "tokens": ["อาหาร", "อร่อย"]})
        predict_model.assert_not_called()
        self.assertEqual(out, "positive")

    def test_classify_phrase_does_not_retry_failed_model(self):
        # วลีกำกวม + ไม่มี clause sentiment cache -> เดิมจะเรียกโมเดล; เมื่อ failed ต้องไม่เรียก
        p = Phrase(surface="คนเยอะ", descriptor_tokens=["คนเยอะ"],
                   clause={"clean": "คนเยอะ", "tokens": ["คนเยอะ"]})
        with mock.patch.object(config, "get_use_model", return_value=True), \
             mock.patch.object(sentiment, "_model_status", "failed"), \
             mock.patch.object(sentiment, "_predict_model") as predict_model:
            out = sentiment.classify_phrase(p)
        predict_model.assert_not_called()
        self.assertIn(out, {"positive", "neutral", "negative"})


class TestTruncation(unittest.TestCase):
    def test_predict_model_passes_truncation(self):
        fake_pipe = mock.Mock(return_value=[{"label": "pos"}])
        with mock.patch.object(sentiment, "_load_model", return_value=fake_pipe):
            out = sentiment._predict_model("อร่อย")
        self.assertEqual(out, "positive")
        _, kwargs = fake_pipe.call_args
        self.assertTrue(kwargs.get("truncation"))


class TestBatchInference(unittest.TestCase):
    def test_analyze_all_batches_into_one_model_call(self):
        fake_pipe = mock.Mock(return_value=[
            {"label": "pos"}, {"label": "pos"}, {"label": "neg"},
        ])
        review = {
            "clean": "อาหารอร่อย บริการช้า",
            "tokens": ["อาหาร", "อร่อย", "บริการ", "ช้า"],
            "clauses": [
                {"clean": "อาหารอร่อย", "tokens": ["อาหาร", "อร่อย"]},
                {"clean": "บริการช้า", "tokens": ["บริการ", "ช้า"]},
            ],
        }
        with mock.patch.object(config, "get_use_model", return_value=True), \
             mock.patch.object(sentiment, "_model_status", None), \
             mock.patch.object(sentiment, "_load_model", return_value=fake_pipe):
            out = sentiment.analyze_all([review])
        fake_pipe.assert_called_once()          # 1 review + 2 clauses = call เดียว
        self.assertEqual(out[0]["sentiment"], "positive")
        self.assertEqual(out[0]["clauses"][0]["sentiment"], "positive")
        self.assertEqual(out[0]["clauses"][1]["sentiment"], "negative")

    def test_analyze_all_falls_back_to_lexicon_on_batch_failure(self):
        with mock.patch.object(config, "get_use_model", return_value=True), \
             mock.patch.object(sentiment, "_model_status", None), \
             mock.patch.object(sentiment, "_load_model",
                               side_effect=RuntimeError("no torch")):
            out = sentiment.analyze_all([{
                "clean": "อาหารอร่อย", "tokens": ["อาหาร", "อร่อย"], "clauses": [],
            }])
        self.assertEqual(out[0]["sentiment"], "positive")   # lexicon fallback


if __name__ == "__main__":
    unittest.main()
