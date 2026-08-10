"""Optional Gemini (LLM) extraction engine — an alternative to the rule-based phrase
pipeline. Sends reviews to Google Gemini and asks for structured opinion phrases
(phrase + aspect + sentiment), then maps them into the SAME dashboard contract as
core/phrases/aggregate.build. Imports google.genai lazily so the app still runs
without it; callers fall back to the rule engine when available() is False.
"""
import json
import re

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
    "You analyze Thai restaurant reviews for a customer and owner dashboard. "
    "For each review, return the concrete opinion phrases a customer expressed, in "
    "the customer's own wording (keep intensifiers like มาก). Classify each phrase "
    "into aspect food|service|ambience and sentiment positive|neutral|negative. "
    "Price/value belongs to food. Do not invent phrases not supported by the text. "
    "Keep each phrase SHORT — a few words only (e.g. 'อาหารอร่อยมาก', 'บริการช้า'); "
    "never return a whole sentence. If a review states several opinions, split them "
    "into separate short phrases instead of one long phrase. Also write concise, "
    "plain-Thai narrative analysis: an overview, practical visit tips, one summary "
    "per relevant aspect, and evidence-led owner actions. Every narrative item MUST "
    "cite one or more input review indices that directly support it. Never invent "
    "facts, causes, counts, percentages, prices, times, or facilities. Only mention "
    "a number when that exact number appears in a cited review. Omit unsupported "
    "items. Every narrative item must also return short evidence_quotes copied "
    "VERBATIM from its cited reviews; never paraphrase these quotes and never invert "
    "their meaning or sentiment. Do not mention AI or the analysis process."
)

_EVIDENCE_INDICES_SCHEMA = {
    "type": "array",
    "items": {"type": "integer"},
    "minItems": 1,
    "maxItems": 8,
}

_EVIDENCE_QUOTES_SCHEMA = {
    "type": "array",
    "items": {"type": "string"},
    "minItems": 1,
    "maxItems": 8,
}

_OVERVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "detail": {"type": "string"},
        "evidence_indices": _EVIDENCE_INDICES_SCHEMA,
        "evidence_quotes": _EVIDENCE_QUOTES_SCHEMA,
    },
    "required": ["headline", "detail", "evidence_indices", "evidence_quotes"],
}

_VISIT_TIP_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "detail": {"type": "string"},
        "advice": {"type": "string"},
        "aspect": {"type": "string", "enum": ["food", "service", "ambience"]},
        "sentiment": {
            "type": "string", "enum": ["positive", "neutral", "negative"]
        },
        "evidence_indices": _EVIDENCE_INDICES_SCHEMA,
        "evidence_quotes": _EVIDENCE_QUOTES_SCHEMA,
    },
    "required": [
        "title", "detail", "advice", "aspect", "sentiment", "evidence_indices",
        "evidence_quotes",
    ],
}

_ASPECT_NARRATIVE_SCHEMA = {
    "type": "object",
    "properties": {
        "aspect": {"type": "string", "enum": ["food", "service", "ambience"]},
        "headline": {"type": "string"},
        "detail": {"type": "string"},
        "evidence_indices": _EVIDENCE_INDICES_SCHEMA,
        "evidence_quotes": _EVIDENCE_QUOTES_SCHEMA,
    },
    "required": [
        "aspect", "headline", "detail", "evidence_indices", "evidence_quotes"
    ],
}

_ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "aspect": {"type": "string", "enum": ["food", "service", "ambience"]},
        "title": {"type": "string"},
        "reason": {"type": "string"},
        "action": {"type": "string"},
        "evidence_indices": _EVIDENCE_INDICES_SCHEMA,
        "evidence_quotes": _EVIDENCE_QUOTES_SCHEMA,
    },
    "required": [
        "aspect", "title", "reason", "action", "evidence_indices", "evidence_quotes"
    ],
}

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
        },
        "analysis": {
            "type": "object",
            "properties": {
                "overview": _OVERVIEW_SCHEMA,
                "visit_tips": {
                    "type": "array", "items": _VISIT_TIP_SCHEMA, "maxItems": 5
                },
                "aspect_summaries": {
                    "type": "array", "items": _ASPECT_NARRATIVE_SCHEMA,
                    "maxItems": 3,
                },
                "actions": {
                    "type": "array", "items": _ACTION_SCHEMA, "maxItems": 3
                },
            },
            "required": ["overview", "visit_tips", "aspect_summaries", "actions"],
        },
    },
    "required": ["reviews", "analysis"],
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


def _source_text(value) -> str:
    return "".join(str(value or "").casefold().split())


def payload_occurrences(payload: dict, reviews: list | None = None) -> list[dict]:
    """Validate structured output while preserving its review index for evaluation."""
    occurrences = []
    for r in payload.get("reviews", []):
        index = r.get("index")
        if not isinstance(index, int) or index < 0:
            continue
        if reviews is not None and index >= len(reviews):
            continue
        for item in r.get("phrases", []):
            aspect = _ASPECT_KEY.get(item.get("aspect"))
            sentiment = item.get("sentiment")
            text = (item.get("phrase") or "").strip()
            if not aspect or sentiment not in _SENTS or not text:
                continue
            if len(text) > _MAX_PHRASE_CHARS:        # ทั้งประโยคหลุดมา -> ข้าม
                continue
            if reviews is not None:
                review_text = reviews[index].get("text") or reviews[index].get("clean")
                if _source_text(text) not in _source_text(review_text):
                    continue
            occurrences.append({
                "index": index,
                "text": text,
                "aspect": aspect,
                "sentiment": sentiment,
            })
    return occurrences


def _to_contract(payload: dict, reviews: list | None = None) -> dict:
    phrases = []
    for item in payload_occurrences(payload, reviews=reviews):
        p = Phrase(surface=item["text"])
        p.aspect, p.sentiment = item["aspect"], item["sentiment"]
        p.review_index = item["index"]
        p.display = item["text"]
        p.agg_key = item["text"]          # identical phrasings merge & count
        p.label = item["text"]
        phrases.append(p)
    return aggregate.build(phrases)


_NUMBER_RE = re.compile(r"[0-9๐-๙]+(?:[.,][0-9๐-๙]+)?|%")


def _evidence_indices(raw, reviews: list) -> list[int]:
    return list(dict.fromkeys(
        value for value in (raw or [])
        if isinstance(value, int) and 0 <= value < len(reviews)
    ))[:8]


def _validated_text(value, evidence: list[int], reviews: list, limit: int) -> str:
    text = " ".join(str(value or "").split()).strip()
    if not text or len(text) > limit:
        return ""
    source = " ".join(str(reviews[index].get("text") or "") for index in evidence)
    for token in _NUMBER_RE.findall(text):
        if token not in source:
            return ""
    return text


def _narrative_item(raw: dict, reviews: list, fields: dict[str, int]) -> dict | None:
    evidence = _evidence_indices(raw.get("evidence_indices"), reviews)
    if not evidence:
        return None
    quotes = []
    for value in (raw.get("evidence_quotes") or [])[:8]:
        quote = " ".join(str(value or "").split()).strip()
        if not quote or len(quote) > 120:
            continue
        if any(_source_text(quote) in _source_text(reviews[index].get("text"))
               for index in evidence):
            quotes.append(quote)
    quotes = list(dict.fromkeys(quotes))
    if not quotes:
        return None
    evidence = [
        index for index in evidence
        if any(_source_text(quote) in _source_text(reviews[index].get("text"))
               for quote in quotes)
    ]
    if not evidence:
        return None
    item = {
        field: _validated_text(raw.get(field), evidence, reviews, limit)
        for field, limit in fields.items()
    }
    if not all(item.values()):
        return None
    item["evidence_review_ids"] = [f"R{index + 1:03d}" for index in evidence]
    item["evidence_quotes"] = quotes
    item["review_count"] = len(evidence)
    return item


def narrative_from_payload(payload: dict, reviews: list) -> dict:
    """Validate Gemini prose and attach stable source-review IDs.

    Numeric claims are accepted only when the exact number occurs in cited reviews.
    Items without valid evidence are discarded instead of being shown as facts.
    """
    analysis = payload.get("analysis") or {}
    overview = _narrative_item(
        analysis.get("overview") or {}, reviews,
        {"headline": 120, "detail": 420},
    )

    visit_tips = []
    for raw in (analysis.get("visit_tips") or [])[:5]:
        aspect = _ASPECT_KEY.get(raw.get("aspect"))
        sentiment = raw.get("sentiment")
        item = _narrative_item(
            raw, reviews, {"title": 120, "detail": 300, "advice": 220}
        )
        if item and aspect and sentiment in _SENTS:
            from core import preprocess, sentiment as sentiment_engine
            quote_sentiments = {
                sentiment_engine.predict(preprocess.preprocess_review(quote), use_model=False)
                for quote in item.get("evidence_quotes", [])
            } - {"neutral"}
            if quote_sentiments and sentiment not in quote_sentiments:
                continue
            item.update({"aspect": aspect, "sentiment": sentiment})
            visit_tips.append(item)

    aspect_summaries = []
    seen_aspects = set()
    for raw in (analysis.get("aspect_summaries") or [])[:3]:
        aspect = _ASPECT_KEY.get(raw.get("aspect"))
        item = _narrative_item(
            raw, reviews, {"headline": 120, "detail": 360}
        )
        if item and aspect and aspect not in seen_aspects:
            item["aspect"] = aspect
            aspect_summaries.append(item)
            seen_aspects.add(aspect)

    actions = []
    seen_actions = set()
    for raw in (analysis.get("actions") or [])[:3]:
        aspect = _ASPECT_KEY.get(raw.get("aspect"))
        item = _narrative_item(
            raw, reviews, {"title": 120, "reason": 300, "action": 360}
        )
        if item and aspect and aspect not in seen_actions:
            item["aspect"] = aspect
            actions.append(item)
            seen_actions.add(aspect)

    return {
        "overview": overview or {},
        "visit_tips": visit_tips,
        "aspect_summaries": aspect_summaries,
        "actions": actions,
    }


def _build_prompt(reviews: list) -> str:
    lines = ["Reviews (one per line, prefixed by index):"]
    for i, r in enumerate(reviews):
        text = (r.get("text") or r.get("clean") or "").replace("\n", " ").strip()
        lines.append(f"{i}\t{text}")
    lines.append(
        "\nReturn JSON matching the schema: an object with key \"reviews\", a list of "
        "{index, phrases:[{phrase, aspect, sentiment}]} — one entry per input index; "
        "and key \"analysis\" containing the evidence-led Thai narrative."
    )
    return "\n".join(lines)


def extract_payload(reviews: list) -> dict:
    """Call Gemini once and return its validated-schema JSON payload."""
    client = _client()
    gen_config = {
        "system_instruction": _SYSTEM,
        "response_mime_type": "application/json",
        "response_schema": _SCHEMA,
    }
    try:
        resp = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=_build_prompt(reviews),
            config=gen_config,
        )
        return json.loads(resp.text)
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()


def extract_bundle(reviews: list) -> tuple[dict, dict]:
    """Return phrase contract and validated narrative from one Gemini request."""
    payload = extract_payload(reviews)
    return _to_contract(payload, reviews=reviews), narrative_from_payload(payload, reviews)


def extract_all(reviews: list) -> dict:
    """Call Gemini once for the batch and return the dashboard contract. Raises on
    API/parse failure; callers (pipeline) catch and fall back to the rule engine."""
    return extract_bundle(reviews)[0]
