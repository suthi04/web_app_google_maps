"""
eval/evaluate.py
================
ประเมินความแม่นยำของโมเดลวิเคราะห์อารมณ์ เทียบกับชุดทดสอบที่ติด label มือ
(data/labeled_reviews.json) — นี่คือหลักฐานเชิงปริมาณสำหรับบทที่ 4 ของวิทยานิพนธ์

วัดอะไรบ้าง:
  - Accuracy
  - Precision / Recall / F1 รายคลาส (positive / neutral / negative)
  - Macro-F1 และ Weighted-F1
  - Confusion Matrix (3x3)
  - Cohen's Kappa (ระดับความสอดคล้องเหนือความบังเอิญ)

วิธีรัน (จาก root ของโปรเจกต์):
    python eval/evaluate.py                 # ประเมิน engine ปัจจุบัน (demo=lexicon)
    USE_MODEL=1 python eval/evaluate.py      # ประเมิน WangchanBERTa จริง

ผลลัพธ์: พิมพ์ออกจอ + บันทึก eval/report.txt และ eval/confusion_matrix.csv
(ถ้ามี matplotlib จะบันทึกภาพ eval/confusion_matrix.png ให้ด้วย)

หมายเหตุ: คำนวณ metric เองทั้งหมด (ไม่พึ่ง scikit-learn) เพื่อให้รันได้ทุกเครื่อง
"""
import json
import math
import os
import sys

# ให้ import core/ และ config ได้เมื่อรันจาก root
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core import preprocess, sentiment  # noqa: E402

LABELS = ["positive", "neutral", "negative"]
LABELS_TH = {"positive": "บวก", "neutral": "กลาง", "negative": "ลบ"}


def load_dataset():
    path = os.path.join(ROOT, "data", "labeled_reviews.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [r for r in data["reviews"] if r.get("label") in LABELS]


def predict_all(items):
    y_true, y_pred = [], []
    for it in items:
        pp = preprocess.preprocess_review(it["text"])
        pred = sentiment.predict({"clean": pp["clean"], "tokens": pp["tokens"]})
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


def build_report(items, y_true, y_pred):
    cm = confusion_matrix(y_true, y_pred)
    pcm = per_class_metrics(cm)
    n = len(items)
    accuracy = sum(cm[c][c] for c in LABELS) / n
    macro_f1 = sum(pcm[c]["f1"] for c in LABELS) / len(LABELS)
    weighted_f1 = sum(pcm[c]["f1"] * pcm[c]["support"] for c in LABELS) / n
    kappa = cohen_kappa(y_true, y_pred)

    L = []
    L.append("=" * 60)
    L.append("  InsightReview — รายงานผลการประเมินโมเดลวิเคราะห์อารมณ์")
    L.append("=" * 60)
    L.append(f"  Engine ที่ใช้   : {sentiment.engine_name()}")
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


def save_outputs(report_text, cm):
    eval_dir = os.path.join(ROOT, "eval")
    with open(os.path.join(eval_dir, "report.txt"), "w", encoding="utf-8") as f:
        f.write(report_text + "\n")
    # CSV ของ confusion matrix
    with open(os.path.join(eval_dir, "confusion_matrix.csv"), "w", encoding="utf-8") as f:
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
        fig.savefig(os.path.join(eval_dir, "confusion_matrix.png"), dpi=150)
        return True
    except Exception:
        return False


def main():
    items = load_dataset()
    if not items:
        print("ไม่พบข้อมูลที่ติด label ใน data/labeled_reviews.json")
        return
    y_true, y_pred = predict_all(items)
    report_text, cm = build_report(items, y_true, y_pred)
    print(report_text)
    has_png = save_outputs(report_text, cm)
    print("\nบันทึกแล้ว: eval/report.txt, eval/confusion_matrix.csv"
          + (", eval/confusion_matrix.png" if has_png else " (ติดตั้ง matplotlib เพื่อได้ภาพ heatmap)"))


if __name__ == "__main__":
    main()
