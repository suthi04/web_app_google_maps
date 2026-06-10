"""Phrase: the single data object that flows through the Review Insight stages."""
from dataclasses import dataclass, field


@dataclass
class Phrase:
    surface: str                                  # raw matched span ("อาหาร อร่อย มากๆ")
    head_noun: str | None = None                  # "อาหาร" | "ราคา" | None
    descriptor: str | None = None                 # cleaned joined descriptor ("ไม่แพง")
    descriptor_tokens: list = field(default_factory=list)  # cleaned descriptor tokens
    pattern: str = ""                             # "P1".."P7" | "idiom" | "fallback"
    canonical: str = ""                           # stage 3 output ("อาหารอร่อย")
    display: str = ""                             # natural readable phrase (intensifiers kept)
    agg_key: str = ""                             # normalized grouping key (counting only)
    concept: str = ""                             # stage 4 concept key (== canonical if ungrouped)
    label: str = ""                               # display label
    aspect: str | None = None                     # food | service | atmosphere
    aspect_conf: str = "low"                      # "high" | "medium" | "low"
    sentiment: str | None = None                  # positive | neutral | negative (stage 6)
    clause: dict = field(default_factory=dict)    # source clause for context sentiment
