"""Optional Claude (LLM) extraction engine — an alternative to the rule-based phrase
pipeline. Sends reviews to Claude and asks for structured opinion phrases
(phrase + aspect + sentiment), then maps them into the SAME dashboard contract as
core/phrases/aggregate.build. Imports `anthropic` lazily so the app still runs
without it; callers fall back to the rule engine when available() is False.
"""
import json

import config
from core.phrases.model import Phrase
from core.phrases import aggregate

_MAX_TOKENS = 4000

# LLM aspect labels -> dashboard contract keys
_ASPECT_KEY = {"food": "food", "service": "service",
               "ambience": "ambience", "atmosphere": "ambience"}
_SENTS = {"positive", "neutral", "negative"}

_SYSTEM = (
    "You extract opinion phrases from Thai restaurant reviews for a dashboard. "
    "For each review, return the concrete opinion phrases a customer expressed, in "
    "the customer's own wording (keep intensifiers like มาก). Classify each phrase "
    "into aspect food|service|ambience and sentiment positive|neutral|negative. "
    "Price/value belongs to food. Do not invent phrases not supported by the text."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "reviews": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "phrases": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "phrase": {"type": "string"},
                                "aspect": {"type": "string",
                                           "enum": ["food", "service", "ambience"]},
                                "sentiment": {"type": "string",
                                              "enum": ["positive", "neutral", "negative"]},
                            },
                            "required": ["phrase", "aspect", "sentiment"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["index", "phrases"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["reviews"],
    "additionalProperties": False,
}


def available() -> bool:
    """True only if the SDK is importable AND an API key is configured."""
    if not config.get_anthropic_api_key():
        return False
    try:
        import anthropic  # noqa: F401
    except Exception:
        return False
    return True


def _client():
    import anthropic
    return anthropic.Anthropic()


def _to_contract(payload: dict) -> dict:
    phrases = []
    for r in payload.get("reviews", []):
        for item in r.get("phrases", []):
            aspect = _ASPECT_KEY.get(item.get("aspect"))
            sentiment = item.get("sentiment")
            text = (item.get("phrase") or "").strip()
            if not aspect or sentiment not in _SENTS or not text:
                continue
            p = Phrase(surface=text)
            p.aspect, p.sentiment = aspect, sentiment
            p.display = text
            p.agg_key = text          # identical phrasings merge & count
            p.label = text
            phrases.append(p)
    return aggregate.build(phrases)


def _build_prompt(reviews: list) -> str:
    lines = ["Reviews (one per line, prefixed by index):"]
    for i, r in enumerate(reviews):
        text = (r.get("text") or r.get("clean") or "").replace("\n", " ").strip()
        lines.append(f"{i}\t{text}")
    lines.append(
        "\nReturn JSON matching the schema: an object with key \"reviews\", a list of "
        "{index, phrases:[{phrase, aspect, sentiment}]} — one entry per input index."
    )
    return "\n".join(lines)


def extract_all(reviews: list) -> dict:
    """Call Claude once for the batch and return the dashboard contract. Raises on
    API/parse failure; callers (pipeline) catch and fall back to the rule engine."""
    client = _client()
    resp = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=_MAX_TOKENS,
        system=_SYSTEM,
        messages=[{"role": "user", "content": _build_prompt(reviews)}],
        output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
    )
    text = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), "")
    payload = json.loads(text)
    return _to_contract(payload)
