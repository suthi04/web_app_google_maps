"""Stage 4 — conservative synonym aggregation. Default is identity; merging happens
only via the curated MEMBER_TO_CONCEPT whitelist."""
from core.lexicon import MEMBER_TO_CONCEPT


def aggregate(p):
    """Set p.concept and p.label from the canonical form."""
    hit = MEMBER_TO_CONCEPT.get(p.canonical)
    if hit:
        p.concept, p.label, _aspect = hit
    else:
        p.concept = p.canonical
        p.label = p.canonical
    return p
