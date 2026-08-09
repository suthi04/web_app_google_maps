"""Pure phrase-level metrics: span detection, labels, and annotator agreement."""
from __future__ import annotations

from collections import Counter

from eval.phrase_schema import ASPECTS, SENTIMENTS


def span_iou(a: dict, b: dict) -> float:
    left = max(a["start"], b["start"])
    right = min(a["end"], b["end"])
    intersection = max(0, right - left)
    if intersection == 0:
        return 0.0
    union = max(a["end"], b["end"]) - min(a["start"], b["start"])
    return intersection / union


def match_phrases(
    gold: list,
    predicted: list,
    *,
    partial: bool = False,
    threshold: float = 0.5,
    require_fields: tuple[str, ...] = (),
) -> list[tuple[int, int, float]]:
    """Greedy one-to-one matching, highest overlap first.

    Exact mode requires identical [start,end). Partial mode accepts span IoU >= threshold.
    Optional fields turn this into an end-to-end aspect/sentiment/joint matcher.
    """
    candidates = []
    for gi, g in enumerate(gold):
        for pi, p in enumerate(predicted):
            if any(g.get(field) != p.get(field) for field in require_fields):
                continue
            score = span_iou(g, p)
            if partial:
                if score < threshold:
                    continue
            elif g["start"] != p["start"] or g["end"] != p["end"]:
                continue
            else:
                score = 1.0
            candidates.append((score, gi, pi))

    matches, used_gold, used_pred = [], set(), set()
    for score, gi, pi in sorted(candidates, reverse=True):
        if gi in used_gold or pi in used_pred:
            continue
        used_gold.add(gi)
        used_pred.add(pi)
        matches.append((gi, pi, score))
    return matches


def prf(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def detection_metrics(gold: list, predicted: list, **match_kwargs) -> tuple[dict, list]:
    matches = match_phrases(gold, predicted, **match_kwargs)
    tp = len(matches)
    return prf(tp, len(predicted) - tp, len(gold) - tp), matches


def classification_metrics(
    gold: list,
    predicted: list,
    matches: list,
    field: str,
    labels: tuple[str, ...],
) -> dict:
    pairs = [(gold[gi][field], predicted[pi][field]) for gi, pi, _ in matches]
    per_class = {}
    for label in labels:
        tp = sum(1 for truth, pred in pairs if truth == label and pred == label)
        fp = sum(1 for truth, pred in pairs if truth != label and pred == label)
        fn = sum(1 for truth, pred in pairs if truth == label and pred != label)
        per_class[label] = prf(tp, fp, fn)
    accuracy = sum(1 for truth, pred in pairs if truth == pred) / len(pairs) if pairs else 0.0
    return {
        "matched": len(pairs),
        "accuracy": accuracy,
        "macro_f1": sum(per_class[x]["f1"] for x in labels) / len(labels),
        "per_class": per_class,
    }


def cohen_kappa(truth: list[str], predicted: list[str], labels: tuple[str, ...]) -> float:
    if len(truth) != len(predicted):
        raise ValueError("truth and predicted must have equal length")
    n = len(truth)
    if not n:
        return 0.0
    observed = sum(a == b for a, b in zip(truth, predicted)) / n
    ca, cb = Counter(truth), Counter(predicted)
    expected = sum((ca[label] / n) * (cb[label] / n) for label in labels)
    return (observed - expected) / (1 - expected) if expected < 1 else 1.0


def evaluate_reviews(gold_reviews: list, predicted_by_id: dict, threshold: float = 0.5) -> dict:
    totals = {name: {"tp": 0, "fp": 0, "fn": 0} for name in (
        "exact", "partial", "partial_aspect", "partial_sentiment", "partial_joint"
    )}
    matched_gold, matched_pred, matched_pairs = [], [], []
    predicted_total = 0

    for review in gold_reviews:
        gold = review.get("phrases", [])
        predicted = predicted_by_id.get(review["id"], [])
        predicted_total += len(predicted)
        configs = {
            "exact": {"partial": False},
            "partial": {"partial": True},
            "partial_aspect": {"partial": True, "require_fields": ("aspect",)},
            "partial_sentiment": {"partial": True, "require_fields": ("sentiment",)},
            "partial_joint": {
                "partial": True, "require_fields": ("aspect", "sentiment")
            },
        }
        partial_matches = []
        for name, kwargs in configs.items():
            metrics, matches = detection_metrics(
                gold, predicted, threshold=threshold, **kwargs
            )
            for key in ("tp", "fp", "fn"):
                totals[name][key] += metrics[key]
            if name == "partial":
                partial_matches = matches
        matched_gold.extend(gold)
        matched_pred.extend(predicted)
        # Store objects directly so classification can run after aggregation.
        base_g = len(matched_gold) - len(gold)
        base_p = len(matched_pred) - len(predicted)
        matched_pairs.extend((base_g + gi, base_p + pi, score)
                             for gi, pi, score in partial_matches)

    report = {
        "reviews": len(gold_reviews),
        "gold_phrases": sum(len(r.get("phrases", [])) for r in gold_reviews),
        "predicted_phrases": predicted_total,
        "partial_iou_threshold": threshold,
    }
    for name, counts in totals.items():
        report[name] = prf(counts["tp"], counts["fp"], counts["fn"])
    report["aspect_on_partial_matches"] = classification_metrics(
        matched_gold, matched_pred, matched_pairs, "aspect", ASPECTS
    )
    report["sentiment_on_partial_matches"] = classification_metrics(
        matched_gold, matched_pred, matched_pairs, "sentiment", SENTIMENTS
    )
    return report


def agreement_report(doc_a: dict, doc_b: dict, threshold: float = 0.5) -> dict:
    # "skipped" means the annotator made no judgment; it must not be interpreted
    # as a deliberate empty-phrase annotation.
    by_b = {r["id"]: r for r in doc_b["reviews"] if r.get("status") != "skipped"}
    shared = [r for r in doc_a["reviews"]
              if r.get("status") != "skipped" and r["id"] in by_b]
    predicted = {rid: r.get("phrases", []) for rid, r in by_b.items()}
    report = evaluate_reviews(shared, predicted, threshold)

    aspect_a, aspect_b, sentiment_a, sentiment_b = [], [], [], []
    for ra in shared:
        rb = by_b[ra["id"]]
        matches = match_phrases(
            ra.get("phrases", []), rb.get("phrases", []),
            partial=True, threshold=threshold,
        )
        for gi, pi, _ in matches:
            ga, pb = ra["phrases"][gi], rb["phrases"][pi]
            aspect_a.append(ga["aspect"]); aspect_b.append(pb["aspect"])
            sentiment_a.append(ga["sentiment"]); sentiment_b.append(pb["sentiment"])
    report["aspect_kappa"] = cohen_kappa(aspect_a, aspect_b, ASPECTS)
    report["sentiment_kappa"] = cohen_kappa(sentiment_a, sentiment_b, SENTIMENTS)
    report["shared_reviews"] = len(shared)
    return report
