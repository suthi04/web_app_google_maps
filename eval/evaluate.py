"""
eval/evaluate.py
================
ประเมินโมเดลวิเคราะห์อารมณ์เทียบกับป้ายอ้างอิงใน data/labeled_reviews.json
ชุดปัจจุบันคือรีวิวจริง Pupen Seafood ที่ AI ติดป้าย และยังรอตรวจโดยมนุษย์

วัดอะไรบ้าง:
  - Accuracy
  - Precision / Recall / F1 รายคลาส (positive / neutral / negative)
  - Macro-F1 และ Weighted-F1
  - Confusion Matrix (3x3)
  - Cohen's Kappa (ระดับความสอดคล้องเหนือความบังเอิญ)

วิธีรัน (จาก root ของโปรเจกต์):
    python eval/evaluate.py                 # ประเมิน engine ปัจจุบัน (demo=lexicon)
    python -m eval.evaluate --engine model  # โมเดลจริง; fail closed ไม่ fallback

ผลลัพธ์: พิมพ์ออกจอ + บันทึก eval/report.txt และ eval/confusion_matrix.csv
(ถ้ามี matplotlib จะบันทึกภาพ eval/confusion_matrix.png ให้ด้วย)

หมายเหตุ: คำนวณ metric เองทั้งหมด (ไม่พึ่ง scikit-learn) เพื่อให้รันได้ทุกเครื่อง
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import sys

# ให้ import core/ และ config ได้เมื่อรันจาก root
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core import preprocess, sentiment  # noqa: E402

LABELS = ["positive", "neutral", "negative"]
LABELS_TH = {"positive": "บวก", "neutral": "กลาง", "negative": "ลบ"}


def load_dataset(path=None):
    path = path or os.path.join(ROOT, "data", "labeled_reviews.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [r for r in data["reviews"] if r.get("label") in LABELS]


def load_evaluation_document(path):
    """Join optional audit metadata only when it matches the actual text/labels."""
    dataset_path = Path(path)
    dataset_bytes = dataset_path.read_bytes()
    document = json.loads(dataset_bytes)
    provenance_path = dataset_path.with_suffix(".provenance.json")
    if provenance_path.exists():
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        if provenance.get("dataset_sha256") != hashlib.sha256(dataset_bytes).hexdigest():
            raise ValueError("Dataset changed: update its provenance before reporting audited results.")
        plain = [(r["text"], r["label"]) for r in document["reviews"]]
        audited = [(r["text"], r["label"]) for r in provenance["reviews"]]
        if plain != audited:
            raise ValueError("Provenance text/labels do not match the evaluation dataset.")
        document = provenance
    return document


def predict_all(items, use_model=None, *, strict_model=False):
    y_true, y_pred = [], []
    for it in items:
        pp = preprocess.preprocess_review(it["text"])
        if strict_model:
            # Research runs must fail rather than silently switch to lexicon.
            pred = sentiment._predict_model(pp["clean"])
        else:
            pred = sentiment.predict(
                {"clean": pp["clean"], "tokens": pp["tokens"]},
                use_model=use_model,
            )
        y_true.append(it["label"])
        y_pred.append(pred)
    return y_true, y_pred


def confusion_matrix(y_true, y_pred):
    cm = {t: {p: 0 for p in LABELS} for t in LABELS}
    for t, p in zip(y_true, y_pred):
        cm[t][p] += 1
    return cm


def per_class_metrics(cm):
    """คืน dict: label -> {precision, recall, f1, support}"""
    out = {}
    for c in LABELS:
        tp = cm[c][c]
        fp = sum(cm[t][c] for t in LABELS if t != c)      # ทายเป็น c แต่จริงไม่ใช่
        fn = sum(cm[c][p] for p in LABELS if p != c)      # จริงเป็น c แต่ทายพลาด
        support = sum(cm[c][p] for p in LABELS)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        out[c] = {"precision": precision, "recall": recall, "f1": f1, "support": support}
    return out


def cohen_kappa(y_true, y_pred):
    n = len(y_true)
    if n == 0:
        return 0.0
    po = sum(1 for t, p in zip(y_true, y_pred) if t == p) / n
    pe = 0.0
    for c in LABELS:
        p_true = sum(1 for t in y_true if t == c) / n
        p_pred = sum(1 for p in y_pred if p == c) / n
        pe += p_true * p_pred
    return (po - pe) / (1 - pe) if (1 - pe) else 0.0


def build_report(
    items, y_true, y_pred, *, title=None, dataset_label=None, engine_label=None
):
    cm = confusion_matrix(y_true, y_pred)
    pcm = per_class_metrics(cm)
    n = len(items)
    accuracy = sum(cm[c][c] for c in LABELS) / n
    macro_f1 = sum(pcm[c]["f1"] for c in LABELS) / len(LABELS)
    weighted_f1 = sum(pcm[c]["f1"] * pcm[c]["support"] for c in LABELS) / n
    kappa = cohen_kappa(y_true, y_pred)

    L = []
    L.append("=" * 60)
    L.append(title or "  InsightReview — รายงานผลการประเมินโมเดลวิเคราะห์อารมณ์")
    L.append("=" * 60)
    L.append(f"  Engine ที่ใช้   : {engine_label or sentiment.engine_name()}")
    if dataset_label:
        L.append(f"  ชุดข้อมูล       : {dataset_label}")
    L.append(f"  จำนวนตัวอย่าง  : {n} รีวิว")
    L.append(f"  Accuracy       : {accuracy:.4f}  ({accuracy*100:.1f}%)")
    L.append(f"  Macro-F1       : {macro_f1:.4f}")
    L.append(f"  Weighted-F1    : {weighted_f1:.4f}")
    L.append(f"  Cohen's Kappa  : {kappa:.4f}")
    L.append("")
    L.append("  Precision / Recall / F1 รายคลาส")
    L.append("  " + "-" * 56)
    L.append(f"  {'class':<12}{'precision':>11}{'recall':>10}{'f1':>10}{'support':>10}")
    for c in LABELS:
        m = pcm[c]
        L.append(f"  {c:<12}{m['precision']:>11.3f}{m['recall']:>10.3f}"
                 f"{m['f1']:>10.3f}{m['support']:>10}")
    L.append("")
    L.append("  Confusion Matrix  (แถว = จริง, คอลัมน์ = ทำนาย)")
    L.append("  " + "-" * 56)
    header = "  {:<12}".format("true\\pred") + "".join(f"{LABELS_TH[p]:>9}" for p in LABELS)
    L.append(header)
    for t in LABELS:
        row = "  {:<12}".format(LABELS_TH[t]) + "".join(f"{cm[t][p]:>9}" for p in LABELS)
        L.append(row)
    L.append("=" * 60)
    return "\n".join(L), cm


def save_outputs(report_text, cm, *, prefix=""):
    eval_dir = os.path.join(ROOT, "eval")
    with open(os.path.join(eval_dir, f"{prefix}report.txt"), "w", encoding="utf-8") as f:
        f.write(report_text + "\n")
    # CSV ของ confusion matrix
    with open(os.path.join(eval_dir, f"{prefix}confusion_matrix.csv"), "w", encoding="utf-8") as f:
        f.write("true\\pred," + ",".join(LABELS) + "\n")
        for t in LABELS:
            f.write(t + "," + ",".join(str(cm[t][p]) for p in LABELS) + "\n")
    # ภาพ heatmap (ถ้ามี matplotlib)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        mat = [[cm[t][p] for p in LABELS] for t in LABELS]
        fig, ax = plt.subplots(figsize=(4.6, 4.2))
        im = ax.imshow(mat, cmap="Purples")
        ax.set_xticks(range(3)); ax.set_xticklabels(LABELS, rotation=20)
        ax.set_yticks(range(3)); ax.set_yticklabels(LABELS)
        ax.set_xlabel("Predicted"); ax.set_ylabel("True")
        ax.set_title("Confusion Matrix")
        for i in range(3):
            for j in range(3):
                ax.text(j, i, mat[i][j], ha="center", va="center",
                        color="white" if mat[i][j] > max(max(mat)) / 2 else "black")
        fig.colorbar(im, fraction=0.046, pad=0.04)
        fig.tight_layout()
        fig.savefig(os.path.join(eval_dir, f"{prefix}confusion_matrix.png"), dpi=150)
        plt.close(fig)
        return True
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Evaluate review sentiment with source and prediction evidence.")
    parser.add_argument("--engine", choices=("current", "model", "rule"), default="current")
    parser.add_argument("--dataset", default=os.path.join(ROOT, "data", "labeled_reviews.json"))
    args = parser.parse_args()
    with open(args.dataset, "rb") as handle:
        dataset_bytes = handle.read()
    document = load_evaluation_document(args.dataset)
    items = [row for row in document["reviews"] if row.get("label") in LABELS]
    if not items:
        print("ไม่พบข้อมูลที่ติด label ใน data/labeled_reviews.json")
        return
    use_model = {"current": None, "model": True, "rule": False}[args.engine]
    strict_model = use_model is True or (use_model is None and sentiment.config.get_use_model())
    if strict_model:
        sentiment._load_model()
    y_true, y_pred = predict_all(items, use_model, strict_model=strict_model)
    engine_label = sentiment.engine_name(use_model=use_model)
    dataset_label = document.get("meta", {}).get("dataset_name")
    report_text, cm = build_report(items, y_true, y_pred, dataset_label=dataset_label, engine_label=engine_label)
    evaluated_at = datetime.now(timezone.utc).isoformat()
    annotation = document.get("meta", {}).get("annotation", {})
    evidence = {
        "evaluated_at": evaluated_at,
        "dataset": os.path.relpath(args.dataset, ROOT).replace("\\", "/"),
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "engine": engine_label,
        "model_name": sentiment.config.MODEL_NAME if strict_model else None,
        "model_revision": sentiment.config.MODEL_REVISION if strict_model else None,
        "model_commit": sentiment._model_pipe.model.config._commit_hash if strict_model else None,
        "preprocessing": "core.preprocess.preprocess_review; model receives clean text",
        "max_length": 512 if strict_model else None,
        "annotation": annotation,
        "versions": {name: importlib.metadata.version(name) for name in ("pythainlp", "transformers", "torch") if importlib.util.find_spec(name)},
        "predictions": [{"id": item.get("id"), "text": item["text"],
                         "reference_label": truth, "predicted_label": prediction,
                         "correct": truth == prediction, "source": item.get("source")}
                        for item, truth, prediction in zip(items, y_true, y_pred)],
    }
    if annotation:
        report_text += "\n\nAnnotation: " + annotation.get("method", "unspecified")
        report_text += "\nHuman validation: " + str(annotation.get("human_validation", "unspecified"))
        report_text += "\nKappa compares reference labels with model predictions; it is not inter-annotator agreement."
    report_text += f"\nEvaluated at (UTC): {evaluated_at}\nDataset SHA-256: {evidence['dataset_sha256']}"
    if strict_model:
        report_text += f"\nModel: {evidence['model_name']}@{evidence['model_revision']}\nCommit: {evidence['model_commit']}\nFallback: disabled (fail on model errors)"
    print(report_text)
    has_png = save_outputs(report_text, cm)
    with open(os.path.join(ROOT, "eval", "predictions.json"), "w", encoding="utf-8") as handle:
        json.dump(evidence, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print("\nบันทึกแล้ว: eval/report.txt, eval/confusion_matrix.csv"
          + (", eval/confusion_matrix.png" if has_png else " (ติดตั้ง matplotlib เพื่อได้ภาพ heatmap)"))


if __name__ == "__main__":
    main()
