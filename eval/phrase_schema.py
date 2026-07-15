"""Schema utilities shared by phrase annotation and evaluation tools."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile

SCHEMA_VERSION = 1
ASPECTS = ("food", "service", "ambience")
SENTIMENTS = ("positive", "neutral", "negative")


def review_id(text: str) -> str:
    """Stable, content-addressed id; the same review keeps the same id everywhere."""
    normalized = " ".join((text or "").split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]


def find_occurrences(text: str, phrase: str) -> list[tuple[int, int]]:
    """Return all exact, possibly-overlapping occurrences as Python string offsets."""
    if not text or not phrase:
        return []
    out, start = [], 0
    while True:
        pos = text.find(phrase, start)
        if pos < 0:
            return out
        out.append((pos, pos + len(phrase)))
        start = pos + 1


def validate_phrase(review_text: str, phrase: dict, where: str = "phrase") -> None:
    required = {"text", "start", "end", "aspect", "sentiment"}
    missing = sorted(required - set(phrase))
    if missing:
        raise ValueError(f"{where}: missing fields {missing}")

    start, end = phrase["start"], phrase["end"]
    if not isinstance(start, int) or not isinstance(end, int):
        raise ValueError(f"{where}: start/end must be integers")
    if start < 0 or end <= start or end > len(review_text):
        raise ValueError(f"{where}: invalid span [{start}, {end})")
    if review_text[start:end] != phrase["text"]:
        raise ValueError(f"{where}: phrase text does not match review[start:end]")
    if phrase["aspect"] not in ASPECTS:
        raise ValueError(f"{where}: invalid aspect {phrase['aspect']!r}")
    if phrase["sentiment"] not in SENTIMENTS:
        raise ValueError(f"{where}: invalid sentiment {phrase['sentiment']!r}")


def validate_document(doc: dict, *, require_phrases: bool = True) -> None:
    if doc.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"unsupported schema_version {doc.get('schema_version')!r}; "
            f"expected {SCHEMA_VERSION}"
        )
    if not isinstance(doc.get("reviews"), list):
        raise ValueError("document must contain a reviews list")

    seen_reviews = set()
    for i, review in enumerate(doc["reviews"]):
        where = f"reviews[{i}]"
        text = review.get("text")
        rid = review.get("id")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"{where}: text must be a non-empty string")
        if rid != review_id(text):
            raise ValueError(f"{where}: id does not match review text")
        if rid in seen_reviews:
            raise ValueError(f"{where}: duplicate review id {rid}")
        seen_reviews.add(rid)

        if not require_phrases and "phrases" not in review:
            continue
        phrases = review.get("phrases")
        if not isinstance(phrases, list):
            raise ValueError(f"{where}: phrases must be a list")
        seen_phrases = set()
        for j, phrase in enumerate(phrases):
            validate_phrase(text, phrase, f"{where}.phrases[{j}]")
            key = (phrase["start"], phrase["end"], phrase["aspect"], phrase["sentiment"])
            if key in seen_phrases:
                raise ValueError(f"{where}.phrases[{j}]: duplicate annotation")
            seen_phrases.add(key)


def load_document(path: str, *, require_phrases: bool = True) -> dict:
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    validate_document(doc, require_phrases=require_phrases)
    return doc


def save_document(path: str, doc: dict, *, require_phrases: bool = True) -> None:
    """Validate then atomically replace the destination to avoid partial label files."""
    validate_document(doc, require_phrases=require_phrases)
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".phrase-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
