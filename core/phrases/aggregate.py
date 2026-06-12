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
    # buckets[aspect][sentiment][agg_key] = {"count": int, "displays": Counter}
    buckets = {a: {s: {} for s in _SENTS} for a in _ASPECTS}
    for p in phrases:
        if p.aspect not in buckets or p.sentiment not in _SENTS:
            continue
        key = p.agg_key or p.concept or p.canonical
        shown = p.display or p.label or p.canonical
        slot = buckets[p.aspect][p.sentiment]
        if key not in slot:
            slot[key] = {"count": 0, "displays": Counter()}
        slot[key]["count"] += 1
        slot[key]["displays"][shown] += 1

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
                items.append((label, entry["count"]))
            items.sort(key=lambda x: (x[1], len(x[0]), x[0]), reverse=True)
            result[a][s] = [{"word": label, "count": cnt} for label, cnt in items[:TOP_N]]
    return result
