"""Stage 3 — build the canonical phrase string; gated head-noun synthesis."""
from core.lexicon import (
    IDIOMS, INTENSIFIERS, FILLERS, ASPECT_HEAD_NOUN, NO_SYNTH_DESCRIPTORS,
)


def _clean_descriptor(tokens: list) -> str:
    return "".join(t for t in tokens if t not in INTENSIFIERS and t not in FILLERS)


def canonicalize(p):
    if p.pattern == "idiom":
        p.canonical = IDIOMS[p.surface]["canonical"]
        return p

    desc = _clean_descriptor(p.descriptor_tokens)

    if p.head_noun:                                   # bound phrase -> head + descriptor
        p.canonical = p.head_noun + desc
        return p

    # standalone descriptor:
    #  - compounds (เย็นสบาย) and self-contained vibe words (คึกคัก) stay as-is
    #  - every other bare single descriptor is synthesized to head-noun + descriptor
    #    at high confidence (อร่อย->อาหารอร่อย, ช้า->บริการช้า), avoiding bare-word noise
    is_compound = len(p.descriptor_tokens) >= 2
    is_self_contained = any(t in NO_SYNTH_DESCRIPTORS for t in p.descriptor_tokens)
    if is_compound or is_self_contained:
        p.canonical = desc
        return p

    if p.aspect_conf == "high" and p.aspect in ASPECT_HEAD_NOUN:
        p.canonical = ASPECT_HEAD_NOUN[p.aspect] + desc
    else:
        p.canonical = desc
    return p
