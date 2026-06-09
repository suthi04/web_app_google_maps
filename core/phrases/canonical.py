"""Stage 3 — build the canonical phrase string; gated head-noun synthesis."""
from core.lexicon import IDIOMS, INTENSIFIERS, FILLERS, ASPECT_HEAD_NOUN, DESCRIPTOR_ASPECT_HINTS


def _clean_descriptor(tokens: list) -> str:
    return "".join(t for t in tokens if t not in INTENSIFIERS and t not in FILLERS)


def canonicalize(p):
    if p.pattern == "idiom":
        p.canonical = IDIOMS[p.surface]["canonical"]
        return p

    desc = _clean_descriptor(p.descriptor_tokens)

    if p.head_noun:                                   # bound phrase
        p.canonical = p.head_noun + desc
        return p

    # standalone descriptor
    is_compound = len(p.descriptor_tokens) >= 2
    is_hinted = any(
        t in DESCRIPTOR_ASPECT_HINTS and DESCRIPTOR_ASPECT_HINTS[t] != "food"
        for t in p.descriptor_tokens
    )
    if is_compound or is_hinted:
        p.canonical = desc
        return p

    if p.aspect_conf == "high" and p.aspect in ASPECT_HEAD_NOUN:
        p.canonical = ASPECT_HEAD_NOUN[p.aspect] + desc
    else:
        p.canonical = desc
    return p
