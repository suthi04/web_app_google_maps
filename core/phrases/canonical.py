"""Stage 3 — build the canonical merge key AND a natural display string.

`canonical`/`agg_key` are normalized (intensifiers stripped) and used ONLY for
counting. `display` keeps the original wording (intensifiers kept, source order)
and is what the dashboard shows. Head-noun synthesis is gated: only a bare lone
descriptor (no head noun, single descriptor token) gets a synthesized head noun.
"""
from core.lexicon import (
    IDIOMS, INTENSIFIERS, FILLERS, ASPECT_HEAD_NOUN, NO_SYNTH_DESCRIPTORS,
    CUSTOMER_FRIENDLY_CANONICAL, CUSTOMER_FRIENDLY_DISPLAY,
)


def _join(tokens: list, drop_intensifiers: bool) -> str:
    out = []
    for t in tokens:
        if t in FILLERS:
            continue
        if drop_intensifiers and t in INTENSIFIERS:
            continue
        out.append(t)
    return "".join(out)


def _surface_display(p) -> str:
    """Natural display from the matched span: keep intensifiers + word order,
    drop only fillers. (extract.py already excludes intensifiers from
    descriptor_tokens, so surface is the only place they survive.)"""
    return "".join(t for t in p.surface.split() if t not in FILLERS)


def _replace_terms(text: str, replacements: dict) -> str:
    """Replace longest terms first so e.g. โคตรอร่อย wins before อร่อย."""
    for source in sorted(replacements, key=len, reverse=True):
        text = text.replace(source, replacements[source])
    # A slang word may already mean "very" while the source also has มาก.
    while "มากมาก" in text:
        text = text.replace("มากมาก", "มาก")
    while "ดีดี" in text:
        text = text.replace("ดีดี", "ดี")
    while "ดีมากดีมาก" in text:
        text = text.replace("ดีมากดีมาก", "ดีมาก")
    # Several consecutive praise tokens should read as one concise opinion.
    for noisy, concise in (
        ("ดีมากที่สุด", "ดีมาก"),
        ("อร่อยมากดีมาก", "อร่อยมาก"),
        ("อร่อยดีมาก", "อร่อยมาก"),
        ("อร่อยถูกใจ", "อร่อยมาก"),
        ("อร่อยดี", "อร่อย"),
    ):
        text = text.replace(noisy, concise)
    return text


def _make_customer_friendly(p):
    p.canonical = _replace_terms(p.canonical, CUSTOMER_FRIENDLY_CANONICAL)
    p.display = _replace_terms(p.display, CUSTOMER_FRIENDLY_DISPLAY)
    return p


def canonicalize(p):
    if p.pattern == "idiom":
        info = IDIOMS[p.surface]
        p.canonical = info["canonical"]
        p.display = info.get("display", p.canonical)
        return _make_customer_friendly(p)

    key_desc = _join(p.descriptor_tokens, drop_intensifiers=True)    # merge key

    if p.head_noun:                                   # bound phrase -> head + descriptor
        p.canonical = p.head_noun + key_desc
        p.display = _surface_display(p)
        return _make_customer_friendly(p)

    # standalone descriptor:
    #  - compounds (เย็นสบาย) and self-contained vibe words (คึกคัก) stay as-is
    #  - a bare lone descriptor with a high-confidence aspect is synthesized to
    #    head-noun + descriptor (อร่อย -> อาหารอร่อย), avoiding bare-word noise
    is_compound = len(p.descriptor_tokens) >= 2
    is_self_contained = any(t in NO_SYNTH_DESCRIPTORS for t in p.descriptor_tokens)
    if is_compound or is_self_contained:
        p.canonical = key_desc
        p.display = _surface_display(p)
        return _make_customer_friendly(p)

    if p.aspect_conf == "high" and p.aspect in ASPECT_HEAD_NOUN:
        head = ASPECT_HEAD_NOUN[p.aspect]
        p.canonical = head + key_desc
        p.display = head + _surface_display(p)
    else:
        p.canonical = key_desc
        p.display = _surface_display(p)
    return _make_customer_friendly(p)
