"""Stage 2 — quality filtering. Decides worthiness; sets provisional aspect +
confidence for bare-descriptor (P7) phrases so stage 3 can gate synthesis."""
from core.lexicon import META_VERBS, DESCRIPTOR_ASPECT_HINTS

MIN_LEN = 2


def _provisional_aspect(p, clause_aspects):
    """Return (aspect, conf) for a standalone descriptor phrase, or (None, 'low')."""
    for tok in p.descriptor_tokens:
        if tok in DESCRIPTOR_ASPECT_HINTS:
            return DESCRIPTOR_ASPECT_HINTS[tok], "high"
    joined = "".join(p.descriptor_tokens)
    if joined in DESCRIPTOR_ASPECT_HINTS:
        return DESCRIPTOR_ASPECT_HINTS[joined], "high"
    if len(clause_aspects) == 1:
        return clause_aspects[0], "high"
    return None, "low"


def filter_phrases(phrases: list, clause_aspects: list) -> list:
    out = []
    for p in phrases:
        if p.pattern == "idiom":
            out.append(p)
            continue

        if any(t in META_VERBS for t in p.descriptor_tokens):
            continue

        if p.head_noun and p.descriptor_tokens:
            out.append(p)
            continue

        if p.head_noun and not p.descriptor_tokens:
            continue

        if p.descriptor_tokens:
            joined = "".join(p.descriptor_tokens)
            if len(joined) < MIN_LEN:
                continue
            asp, conf = _provisional_aspect(p, clause_aspects)
            is_compound = len(p.descriptor_tokens) >= 2
            is_hinted = any(t in DESCRIPTOR_ASPECT_HINTS for t in p.descriptor_tokens)
            if is_compound or is_hinted:
                p.aspect, p.aspect_conf = asp, (conf if asp else "low")
                out.append(p)
                continue
            if conf == "high" and asp:
                p.aspect, p.aspect_conf = asp, "high"
                out.append(p)
                continue
            # bare single descriptor, low confidence -> drop (no hallucination)
            continue
    return out
