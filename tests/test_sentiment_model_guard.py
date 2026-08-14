"""โหมดโมเดล: เมื่อโมเดลล้มเหลวแล้ว (_model_status == "failed") ต้อง "ไม่" พยายาม
โหลด/เรียกโมเดลซ้ำทุกข้อความ (กันการวิเคราะห์ลากยาวหลายนาทีใน failure mode),
ต้องส่ง truncation=True กัน token เกิน, และ analyze_all ต้อง batch เป็น call เดียว"""
import os
import sys
import threading
import time
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


class TestModelConcurrency(unittest.TestCase):
    def test_inference_gate_limits_three_jobs_to_two_model_calls(self):
        state = {"active": 0, "maximum": 0}
        state_lock = threading.Lock()
        two_entered = threading.Event()
        release = threading.Event()

        def fake_pipe(_text, **_kwargs):
            with state_lock:
                state["active"] += 1
                state["maximum"] = max(state["maximum"], state["active"])
                if state["active"] == 2:
                    two_entered.set()
            release.wait(2)
            with state_lock:
                state["active"] -= 1
            return [{"label": "pos"}]

        results = []
        with mock.patch.object(
            sentiment, "_model_inference_gate", threading.BoundedSemaphore(2)
        ), mock.patch.object(sentiment, "_load_model", return_value=fake_pipe):
            threads = [
                threading.Thread(
                    target=lambda: results.append(sentiment._predict_model("อร่อย"))
                )
                for _ in range(3)
            ]
            for thread in threads:
                thread.start()
            self.assertTrue(two_entered.wait(1), "two model calls did not start")
            time.sleep(0.05)
            with state_lock:
                self.assertEqual(state["active"], 2)
            release.set()
            for thread in threads:
                thread.join(2)

        self.assertEqual(state["maximum"], 2)
        self.assertEqual(results, ["positive"] * 3)

    def test_lazy_model_is_loaded_once_when_workers_race(self):
        fake_model = object()
        calls = 0
        calls_lock = threading.Lock()

        def fake_pipeline():
            nonlocal calls
            with calls_lock:
                calls += 1
            time.sleep(0.05)
            return fake_model

        loaded = []
        with mock.patch.object(sentiment, "_model_pipe", None), \
             mock.patch.object(sentiment, "_model_status", None), \
             mock.patch.object(
                 sentiment, "_build_model_pipeline", side_effect=fake_pipeline
             ):
            threads = [
                threading.Thread(target=lambda: loaded.append(sentiment._load_model()))
                for _ in range(3)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(2)

        self.assertEqual(calls, 1)
        self.assertEqual(loaded, [fake_model] * 3)


if __name__ == "__main__":
    unittest.main()
