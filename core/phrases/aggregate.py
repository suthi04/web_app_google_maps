"""Stage 7 — count phrases by (aspect, sentiment, agg_key) into the dashboard
contract: {aspect: {positive:[{word,count}], neutral:[...], negative:[...]}}.

The shown label is the most frequent `display` among the merged occurrences (so a
repeated opinion keeps real review wording while its count rises). Falls back to
label/canonical when display is empty (e.g. LLM phrases that set display directly).
"""
from collections import Counter

from core.lexicon import ASPECT_LEXICON

_SENTS = ("positive", "neutral", "negative")
_ASPECTS = tuple(ASPECT_LEXICON.keys())   # food, service, ambience
TOP_N = 6


def build(phrases: list) -> dict:
    # buckets[aspect][sentiment][agg_key] keeps both occurrence count and the
    # unique source reviews.  The latter is the research-safe denominator shown
    # in evidence links; repeating a phrase inside one review must not look like
    # independent customer support.
    buckets = {a: {s: {} for s in _SENTS} for a in _ASPECTS}
    for p in phrases:
        if p.aspect not in buckets or p.sentiment not in _SENTS:
            continue
        key = p.agg_key or p.concept or p.canonical
        shown = p.display or p.label or p.canonical
        slot = buckets[p.aspect][p.sentiment]
        if key not in slot:
            slot[key] = {
                "count": 0,
                "displays": Counter(),
                "review_indices": set(),
            }
        slot[key]["count"] += 1
        slot[key]["displays"][shown] += 1
        if isinstance(p.review_index, int) and p.review_index >= 0:
            slot[key]["review_indices"].add(p.review_index)

    result = {}
    for a in _ASPECTS:
        result[a] = {}
        for s in _SENTS:
            items = []
            for entry in buckets[a][s].values():
                # most common display; tie -> shorter, then lexicographic
                label = sorted(
                    entry["displays"].items(),
                    key=lambda x: (-x[1], len(x[0]), x[0]),
                )[0][0]
                evidence_ids = [
                    f"R{index + 1:03d}"
                    for index in sorted(entry["review_indices"])
                ]
                items.append({
                    "word": label,
                    "count": entry["count"],
                    "review_count": len(evidence_ids),
                    "evidence_review_ids": evidence_ids,
                })
            items.sort(
                key=lambda item: (
                    item["review_count"], item["count"],
                    len(item["word"]), item["word"],
                ),
                reverse=True,
            )
            result[a][s] = items[:TOP_N]
    return result
