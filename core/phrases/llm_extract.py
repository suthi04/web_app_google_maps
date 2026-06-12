"""Optional Gemini (LLM) extraction engine — an alternative to the rule-based phrase
pipeline. Sends reviews to Google Gemini and asks for structured opinion phrases
(phrase + aspect + sentiment), then maps them into the SAME dashboard contract as
core/phrases/aggregate.build. Imports google.genai lazily so the app still runs
without it; callers fall back to the rule engine when available() is False.
"""
import json

import config
from core.phrases.model import Phrase
from core.phrases import aggregate

# LLM aspect labels -> dashboard contract keys
_ASPECT_KEY = {"food": "food", "service": "service",
               "ambience": "ambience", "atmosphere": "ambience"}
_SENTS = {"positive", "neutral", "negative"}

# วลีที่ยาวเกินนี้ถือว่าเป็น "ทั้งประโยค" ที่หลุดมา ไม่ใช่วลีความเห็นกระชับ -> ตัดทิ้ง
# (วลีไทยที่ดีมักสั้น เช่น "อาหารอร่อยมาก", "บริการช้า"; ประโยคเต็มมักยาวกว่ามาก)
_MAX_PHRASE_CHARS = 40

_SYSTEM = (
    "You extract opinion phrases from Thai restaurant reviews for a dashboard. "
    "For each review, return the concrete opinion phrases a customer expressed, in "
    "the customer's own wording (keep intensifiers like มาก). Classify each phrase "
    "into aspect food|service|ambience and sentiment positive|neutral|negative. "
    "Price/value belongs to food. Do not invent phrases not supported by the text. "
    "Keep each phrase SHORT — a few words only (e.g. 'อาหารอร่อยมาก', 'บริการช้า'); "
    "never return a whole sentence. If a review states several opinions, split them "
    "into separate short phrases instead of one long phrase."
)

# Gemini response schema (OpenAPI-3 subset: NO additionalProperties; enums + required ok)
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
                        },
                    },
                },
                "required": ["index", "phrases"],
            },
        }
    },
    "required": ["reviews"],
}


def available() -> bool:
    """True only if an API key is configured AND the google-genai SDK is importable."""
    if not config.get_gemini_api_key():
        return False
    try:
        from google import genai  # noqa: F401
    except Exception:
        return False
    return True


def _client():
    from google import genai
    return genai.Client(api_key=config.get_gemini_api_key())


def _to_contract(payload: dict) -> dict:
    phrases = []
    for r in payload.get("reviews", []):
        for item in r.get("phrases", []):
            aspect = _ASPECT_KEY.get(item.get("aspect"))
            sentiment = item.get("sentiment")
            text = (item.get("phrase") or "").strip()
            if not aspect or sentiment not in _SENTS or not text:
                continue
            if len(text) > _MAX_PHRASE_CHARS:        # ทั้งประโยคหลุดมา -> ข้าม
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
    """Call Gemini once for the batch and return the dashboard contract. Raises on
    API/parse failure; callers (pipeline) catch and fall back to the rule engine."""
    client = _client()
    gen_config = {
        "system_instruction": _SYSTEM,
        "response_mime_type": "application/json",
        "response_schema": _SCHEMA,
    }
    resp = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=_build_prompt(reviews),
        config=gen_config,
    )
    payload = json.loads(resp.text)
    return _to_contract(payload)
