"""Stage 4 — conservative synonym aggregation. Default is identity; merging happens
only via the curated MEMBER_TO_CONCEPT whitelist. Also sets agg_key, the key the
aggregator counts by (the concept), keeping it distinct from the shown display."""
from core.lexicon import MEMBER_TO_CONCEPT


def aggregate(p):
    """Set p.concept, p.label, and p.agg_key from the canonical form."""
    hit = MEMBER_TO_CONCEPT.get(p.canonical)
    if hit:
        p.concept, p.label, _aspect = hit
    else:
        p.concept = p.canonical
        p.label = p.canonical
    p.agg_key = p.concept
    return p
