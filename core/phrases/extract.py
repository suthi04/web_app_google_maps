"""Stage 1 — lexicon-driven phrase extraction (MWE dict → lexicon grammar).

POS tagging was evaluated and found unreliable on Thai review text (see git history);
the curated lexicon is authoritative. Each strategy suppresses tokens consumed by
earlier ones (overlap suppression).
"""
from core import negation
from core.lexicon import (
    NOUN_TO_ASPECT, DESCRIPTOR_ASPECT_HINTS, IDIOMS, INTENSIFIERS, FILLERS,
    SENTIMENT_WORDS,
)
from core.phrases.model import Phrase

_POLAR = set(SENTIMENT_WORDS["positive"]) | set(SENTIMENT_WORDS["negative"])
_MAX_MWE_SPAN = 4
# Fixed multi-token descriptor compounds (POS can't help; matched like MWEs).
_DESC_MWES = {"เย็นสบาย", "เงียบสงบ"}


def _match_mwes(raw, clause):
    """Longest-match idioms (pattern 'idiom') and fixed descriptor compounds
    (pattern 'P7', aspect preset from hints)."""
    used = [False] * len(raw)
    out, i, n = [], 0, len(raw)
    while i < n:
        matched = False
        for span in range(min(_MAX_MWE_SPAN, n - i), 0, -1):
            glued = "".join(raw[i:i + span])
            if glued in IDIOMS:
                out.append(Phrase(surface=glued, pattern="idiom", clause=clause))
            elif span >= 2 and glued in _DESC_MWES:
                out.append(Phrase(surface=glued, descriptor_tokens=[glued],
                                  pattern="P7",
                                  aspect=DESCRIPTOR_ASPECT_HINTS.get(glued),
                                  aspect_conf="high", clause=clause))
            else:
                continue
            for k in range(i, i + span):
                used[k] = True
            i += span
            matched = True
            break
        if not matched:
            i += 1
    return out, used


def is_noun(tok):
    return tok in NOUN_TO_ASPECT


def is_desc(tok):
    return negation.word_polarity(tok) != 0 or tok in DESCRIPTOR_ASPECT_HINTS


def is_neg(tok):
    return tok in negation.NEGATORS or tok.startswith("ไม่")


def is_filler(tok):
    return tok in FILLERS


def _collect_descriptor_run(raw, j, n):
    """From index j: collect descriptor tokens, skipping fillers, excluding
    intensifiers. Returns (descriptor_tokens, end_index)."""
    desc = []
    while j < n:
        tok = raw[j]
        if tok in INTENSIFIERS or is_filler(tok):
            j += 1
            continue
        if is_desc(tok):
            desc.append(tok)
            j += 1
            continue
        break
    return desc, j


def _match_grammar(raw, used, clause):
    out, i, n = [], 0, len(raw)
    while i < n:
        if used[i]:
            i += 1
            continue
        a = raw[i]
        b = raw[i + 1] if i + 1 < n else None

        # B1 lexicon-phrase recovery (รอ+นาน -> "รอนาน")
        if b is not None and not used[i + 1] and (a + b) in _POLAR and not is_desc(b):
            if is_noun(a):
                head, dtoks = a, [b]
            else:
                head, dtoks = None, [a + b]
            out.append(Phrase(surface=f"{a} {b}", head_noun=head,
                              descriptor_tokens=dtoks, pattern="P3", clause=clause))
            used[i] = used[i + 1] = True
            i += 2
            continue

        # B2 noun-led: NOUN (NEG)? descriptor-run
        if is_noun(a):
            j = i + 1
            neg = []
            if j < n and is_neg(raw[j]) and j + 1 < n and is_desc(raw[j + 1]):
                neg = [raw[j]]
                j += 1
            desc, j2 = _collect_descriptor_run(raw, j, n)
            if desc:
                out.append(Phrase(surface=" ".join(raw[i:j2]), head_noun=a,
                                  descriptor_tokens=neg + desc,
                                  pattern="P2" if neg else "P1", clause=clause))
                for k in range(i, j2):
                    used[k] = True
                i = j2
                continue

        # B3 standalone descriptor / compound -> P7
        if is_desc(a):
            desc, j2 = _collect_descriptor_run(raw, i, n)
            if desc:
                out.append(Phrase(surface=" ".join(raw[i:j2]), head_noun=None,
                                  descriptor_tokens=desc, pattern="P7", clause=clause))
                for k in range(i, j2):
                    used[k] = True
                i = j2
                continue

        i += 1
    return out


def extract(clause: dict) -> list:
    """Public Stage-1 entry point. `clause` must have 'raw_tokens'."""
    raw = clause.get("raw_tokens") or []
    if not raw:
        return []
    phrases, used = _match_mwes(raw, clause)
    phrases += _match_grammar(raw, used, clause)
    return phrases
