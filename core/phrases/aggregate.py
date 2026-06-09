"""Stage 7 — count phrases by (aspect, sentiment, concept) into the dashboard
contract: {aspect: {positive:[{word,count}], neutral:[...], negative:[...]}}."""
from core.lexicon import ASPECT_LEXICON

_SENTS = ("positive", "neutral", "negative")
_ASPECTS = tuple(ASPECT_LEXICON.keys())   # food, service, ambience
TOP_N = 6


def build(phrases: list) -> dict:
    # buckets[aspect][sentiment][concept] = [count, label]
    buckets = {a: {s: {} for s in _SENTS} for a in _ASPECTS}
    for p in phrases:
        if p.aspect not in buckets or p.sentiment not in _SENTS:
            continue
        slot = buckets[p.aspect][p.sentiment]
        if p.concept in slot:
            slot[p.concept][0] += 1
        else:
            slot[p.concept] = [1, p.label or p.canonical]

    result = {}
    for a in _ASPECTS:
        result[a] = {}
        for s in _SENTS:
            items = [(label, count) for count, label in buckets[a][s].values()]
            items.sort(key=lambda x: (x[1], len(x[0]), x[0]), reverse=True)
            result[a][s] = [{"word": label, "count": cnt} for label, cnt in items[:TOP_N]]
    return result
