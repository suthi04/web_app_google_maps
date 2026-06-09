"""Thin, swappable PyThaiNLP POS wrapper. Never raises; falls back to UNK tags."""
try:
    from pythainlp.tag import pos_tag as _pos_tag
    _OK = True
except Exception:  # pragma: no cover
    _OK = False

# Tag-set constants (orchid_ud). CONFIRM against the installed version at execution.
NOUN_TAGS = {"NOUN", "PROPN", "NCMN", "NCNM", "NPRP"}
STATIVE_TAGS = {"VERB", "ADJ", "VATT", "VSTA"}   # Thai opinion words are stative verbs
ADV_TAGS = {"ADV", "ADVN", "ADVI"}
VERB_TAGS = {"VERB", "VACT"}

_CORPUS = "orchid_ud"


def available() -> bool:
    return _OK


def pos_tag(tokens: list) -> list:
    """Return list of (token, tag). On any failure, tag everything 'UNK'."""
    if not tokens:
        return []
    if not _OK:
        return [(t, "UNK") for t in tokens]
    try:
        return _pos_tag(tokens, corpus=_CORPUS)
    except Exception:  # pragma: no cover
        return [(t, "UNK") for t in tokens]
