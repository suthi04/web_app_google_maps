# Hybrid Keyword Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the dashboard keyword/phrase output genuinely useful — opinion phrases that keep original wording, aggregated by count — and add an optional Claude (LLM) extraction engine with automatic fallback plus a rule-based-vs-LLM comparison.

**Architecture:** Phase 1 improves the existing rule-based phrase pipeline by separating a human-readable `display` string from a normalized `agg_key` used only for counting, and stops over-synthesizing head nouns. Phase 2 adds `core/phrases/llm_extract.py` as a second engine selected via settings, emitting the **same** `keywords` contract and falling back to rule-based when no `ANTHROPIC_API_KEY` is present. Phase 3 adds a comparison script.

**Tech Stack:** Python 3.12, Flask, PyThaiNLP (already present), `anthropic` SDK (new, optional import), `unittest` (repo's test runner — run with `python -m unittest`).

**Conventions for this plan:**
- Run a single test with: `python -m unittest tests.test_<name> -v`
- Run all tests with: `python -m unittest discover -s tests -q`
- The repo has **no pytest**; use `unittest`. Tests live in `tests/` and start with `sys.path.insert(0, ...)` to import the project (copy the header from an existing test such as `tests/test_canonical.py`).
- Aspect key spaces: internal pipeline uses `food/service/atmosphere`; the dashboard contract uses `food/service/ambience`. `_ASPECT_KEY` in `core/pipeline.py` and `core/keywords.py` converts `atmosphere -> ambience`.

---

## File Structure

| File | Responsibility | Phase |
|---|---|---|
| `core/phrases/model.py` | `Phrase` dataclass — add `display`, `agg_key` | 1 |
| `core/phrases/canonical.py` | build natural `display`; gated head-noun synthesis | 1 |
| `core/phrases/synonyms.py` | set `agg_key` (= concept) | 1 |
| `core/phrases/aggregate.py` | group by `agg_key`, label by most-frequent `display` | 1 |
| `core/lexicon.py` | add a few common missing words | 1 |
| `core/sentiment.py` | `classify_phrase` reuses `clause["sentiment"]` | 1 |
| `core/pipeline.py` | per-review error isolation; engine dispatch | 1, 2 |
| `config.py` | testable SECRET_KEY resolver; `extract_engine` setting | 1, 2 |
| `core/phrases/llm_extract.py` | **new** — Claude extraction → contract | 2 |
| `templates/settings.html`, `app.py` | engine toggle UI | 2 |
| `requirements.txt` | add optional `anthropic` | 2 |
| `scripts/compare_engines.py` | **new** — rule vs LLM metrics | 3 |
| `README.md` | methodology fix, `topics`, vocab limitation, LLM engine | 1, 2 |

---

# PHASE 1 — Rule-based quality (no API key needed)

### Task 1: Add `display` and `agg_key` fields to `Phrase`

**Files:**
- Modify: `core/phrases/model.py`
- Test: `tests/test_phrase_model.py` (exists — add a case)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_phrase_model.py`:

```python
    def test_display_and_agg_key_default_empty(self):
        from core.phrases.model import Phrase
        p = Phrase(surface="x")
        self.assertEqual(p.display, "")
        self.assertEqual(p.agg_key, "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_phrase_model -v`
Expected: FAIL with `AttributeError: 'Phrase' object has no attribute 'display'`

- [ ] **Step 3: Add the fields**

In `core/phrases/model.py`, inside the `Phrase` dataclass, add these two lines immediately after the `canonical:` field:

```python
    display: str = ""                             # natural readable phrase (intensifiers kept)
    agg_key: str = ""                             # normalized grouping key (counting only)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_phrase_model -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/phrases/model.py tests/test_phrase_model.py
git commit -m "feat(phrases): add display and agg_key fields to Phrase"
```

---

### Task 2: Build natural `display` and stop over-synthesizing head nouns

**Files:**
- Modify: `core/phrases/canonical.py`
- Test: `tests/test_canonical.py` (exists — add cases)

Current behavior to change: `_clean_descriptor` strips intensifiers from the canonical; the head noun is prepended for every bare descriptor at high confidence. New behavior: `canonical` (the normalized key) stays intensifier-stripped, but a new `display` keeps intensifiers and the source span order, and head-noun synthesis happens **only** for a bare lone descriptor (no head noun, single descriptor token).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_canonical.py` (it already imports `Phrase` and `canonicalize`; mirror its existing import header):

```python
    def test_display_keeps_intensifier(self):
        from core.phrases.model import Phrase
        from core.phrases.canonical import canonicalize
        p = Phrase(surface="บริการ ดี มาก", head_noun="บริการ",
                   descriptor_tokens=["ดี", "มาก"], pattern="P1")
        canonicalize(p)
        self.assertEqual(p.display, "บริการดีมาก")
        self.assertEqual(p.canonical, "บริการดี")   # key strips intensifier

    def test_no_oversynthesis_when_head_noun_present(self):
        from core.phrases.model import Phrase
        from core.phrases.canonical import canonicalize
        p = Phrase(surface="บริการ รอนาน", head_noun="บริการ",
                   descriptor_tokens=["รอนาน"], pattern="P1")
        canonicalize(p)
        # display keeps the natural span; canonical is the merge key
        self.assertEqual(p.display, "บริการรอนาน")
        self.assertEqual(p.canonical, "บริการรอนาน")

    def test_bare_lone_descriptor_still_synthesized(self):
        from core.phrases.model import Phrase
        from core.phrases.canonical import canonicalize
        p = Phrase(surface="อร่อย", descriptor_tokens=["อร่อย"], pattern="P7",
                   aspect="food", aspect_conf="high")
        canonicalize(p)
        self.assertEqual(p.canonical, "อาหารอร่อย")
        self.assertEqual(p.display, "อาหารอร่อย")
```

> Note on `test_no_oversynthesis_*`: the awkward `บริการรอนาน` in the live output came from synthesizing a head noun onto a descriptor run. When the head noun is genuinely part of the source span (`P1` with `head_noun`), the *display* is the natural concatenation; the win is that lone-descriptor `รอนาน` (no head noun) is **not** turned into `บริการรอนาน`, so it merges with other `รอนาน` occurrences. This is covered by Task 3's aggregation test.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_canonical -v`
Expected: FAIL with `AttributeError: ... 'display'` or assertion mismatch.

- [ ] **Step 3: Rewrite `canonical.py`**

Replace the entire body of `core/phrases/canonical.py` with:

```python
"""Stage 3 — build the canonical merge key AND a natural display string.

`canonical`/`agg_key` are normalized (intensifiers stripped) and used ONLY for
counting. `display` keeps the original wording (intensifiers kept, source order)
and is what the dashboard shows. Head-noun synthesis is gated: only a bare lone
descriptor (no head noun, single descriptor token) gets a synthesized head noun.
"""
from core.lexicon import (
    IDIOMS, INTENSIFIERS, FILLERS, ASPECT_HEAD_NOUN, NO_SYNTH_DESCRIPTORS,
)


def _join(tokens: list, drop_intensifiers: bool) -> str:
    out = []
    for t in tokens:
        if t in FILLERS:
            continue
        if drop_intensifiers and t in INTENSIFIERS:
            continue
        out.append(t)
    return "".join(out)


def canonicalize(p):
    if p.pattern == "idiom":
        p.canonical = IDIOMS[p.surface]["canonical"]
        p.display = p.canonical
        return p

    key_desc = _join(p.descriptor_tokens, drop_intensifiers=True)    # merge key
    disp_desc = _join(p.descriptor_tokens, drop_intensifiers=False)  # shown to user

    if p.head_noun:                                   # bound phrase -> head + descriptor
        p.canonical = p.head_noun + key_desc
        p.display = p.head_noun + disp_desc
        return p

    # standalone descriptor:
    #  - compounds (เย็นสบาย) and self-contained vibe words (คึกคัก) stay as-is
    #  - a bare lone descriptor with a high-confidence aspect is synthesized to
    #    head-noun + descriptor (อร่อย -> อาหารอร่อย), avoiding bare-word noise
    is_compound = len(p.descriptor_tokens) >= 2
    is_self_contained = any(t in NO_SYNTH_DESCRIPTORS for t in p.descriptor_tokens)
    if is_compound or is_self_contained:
        p.canonical = key_desc
        p.display = disp_desc
        return p

    if p.aspect_conf == "high" and p.aspect in ASPECT_HEAD_NOUN:
        head = ASPECT_HEAD_NOUN[p.aspect]
        p.canonical = head + key_desc
        p.display = head + disp_desc
    else:
        p.canonical = key_desc
        p.display = disp_desc
    return p
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_canonical -v`
Expected: PASS (all, including pre-existing cases)

- [ ] **Step 5: Commit**

```bash
git add core/phrases/canonical.py tests/test_canonical.py
git commit -m "feat(phrases): natural display string + gated head-noun synthesis"
```

---

### Task 3: Set `agg_key` in synonyms; aggregate by it and label by most-frequent display

**Files:**
- Modify: `core/phrases/synonyms.py`
- Modify: `core/phrases/aggregate.py`
- Test: `tests/test_aggregate.py` (exists — add cases)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_aggregate.py` (mirror its existing import header):

```python
    def _mk(self, aspect, sentiment, agg_key, display, label=None):
        from core.phrases.model import Phrase
        p = Phrase(surface=display)
        p.aspect, p.sentiment = aspect, sentiment
        p.agg_key, p.display = agg_key, display
        p.label = label or display
        return p

    def test_repeats_merge_into_one_count(self):
        from core.phrases.aggregate import build
        phrases = [
            self._mk("service", "negative", "รอนาน", "รอนาน"),
            self._mk("service", "negative", "รอนาน", "รออาหารนาน"),
            self._mk("service", "negative", "รอนาน", "รอนาน"),
        ]
        out = build(phrases)
        neg = out["service"]["negative"]
        self.assertEqual(len(neg), 1)
        self.assertEqual(neg[0]["count"], 3)
        # label = most frequent display ("รอนาน" appears 2x vs "รออาหารนาน" 1x)
        self.assertEqual(neg[0]["word"], "รอนาน")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_aggregate -v`
Expected: FAIL (current `build` groups by `concept`/`label`, not `agg_key`, and labels by `label`, so the count/word assertions fail).

- [ ] **Step 3a: Set `agg_key` in `synonyms.py`**

Replace the body of `core/phrases/synonyms.py` with:

```python
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
```

- [ ] **Step 3b: Rewrite `aggregate.py` to group by `agg_key` and label by most-frequent display**

Replace the entire body of `core/phrases/aggregate.py` with:

```python
"""Stage 7 — count phrases by (aspect, sentiment, agg_key) into the dashboard
contract: {aspect: {positive:[{word,count}], neutral:[...], negative:[...]}}.

The shown label is the most frequent `display` among the merged occurrences (so a
repeated opinion keeps real review wording while its count rises). Falls back to
label/canonical when display is empty (e.g. LLM phrases that set display directly).
"""
from collections import Counter

from core.lexicon import ASPECT_LEXICON

_SENTS = ("positive", "neutral", "negative")
_ASPECTS = tuple(ASPECT_LEXICON.keys())   # food, service, ambience
TOP_N = 6


def build(phrases: list) -> dict:
    # buckets[aspect][sentiment][agg_key] = {"count": int, "displays": Counter}
    buckets = {a: {s: {} for s in _SENTS} for a in _ASPECTS}
    for p in phrases:
        if p.aspect not in buckets or p.sentiment not in _SENTS:
            continue
        key = p.agg_key or p.concept or p.canonical
        shown = p.display or p.label or p.canonical
        slot = buckets[p.aspect][p.sentiment]
        if key not in slot:
            slot[key] = {"count": 0, "displays": Counter()}
        slot[key]["count"] += 1
        slot[key]["displays"][shown] += 1

    result = {}
    for a in _ASPECTS:
        result[a] = {}
        for s in _SENTS:
            items = []
            for entry in buckets[a][s].values():
                # most common display; tie -> shorter, then lexicographic
                label = sorted(
                    entry["displays"].items(),
                    key=lambda x: (-x[1], len(x[0]), x[0]),
                )[0][0]
                items.append((label, entry["count"]))
            items.sort(key=lambda x: (x[1], len(x[0]), x[0]), reverse=True)
            result[a][s] = [{"word": label, "count": cnt} for label, cnt in items[:TOP_N]]
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_aggregate -v`
Expected: PASS (new and pre-existing cases)

- [ ] **Step 5: Commit**

```bash
git add core/phrases/synonyms.py core/phrases/aggregate.py tests/test_aggregate.py
git commit -m "feat(phrases): aggregate by agg_key, label by most-frequent display"
```

---

### Task 4: Expand the lexicon with a few common missing words

**Files:**
- Modify: `core/lexicon.py`
- Test: `tests/test_lexicon_maps.py` (exists — add a case)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_lexicon_maps.py`:

```python
    def test_common_slang_descriptors_present(self):
        from core.lexicon import DESCRIPTOR_ASPECT_HINTS, SENTIMENT_WORDS
        # food slang that customers actually use
        self.assertEqual(DESCRIPTOR_ASPECT_HINTS.get("แซ่บ"), "food")
        self.assertIn("แซ่บ", SENTIMENT_WORDS["positive"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_lexicon_maps -v`
Expected: FAIL (`แซ่บ` not present).

- [ ] **Step 3: Add the words**

In `core/lexicon.py`:

1. In `SENTIMENT_WORDS["positive"]`, append `"แซ่บ", "จี๊ดจ๊าด"` to the list.
2. In `DESCRIPTOR_ASPECT_HINTS`, in the `# food-bound descriptors` group, add:

```python
    "แซ่บ": "food", "จี๊ดจ๊าด": "food", "กลมกล่อม": "food", "ชุ่มฉ่ำ": "food",
```

> Keep the additions conservative and food/sensory only — do not add ambiguous words. The README task documents this as a known, bounded vocabulary limitation.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_lexicon_maps -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/lexicon.py tests/test_lexicon_maps.py
git commit -m "feat(lexicon): add common Thai food slang descriptors"
```

---

### Task 5: `classify_phrase` reuses the clause's already-computed sentiment

**Files:**
- Modify: `core/sentiment.py` (the `classify_phrase` function)
- Test: `tests/test_phrase_sentiment.py` (exists — add a case)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_phrase_sentiment.py`:

```python
    def test_ambiguous_phrase_reuses_clause_sentiment_no_model_call(self):
        from unittest import mock
        from core import sentiment
        from core.phrases.model import Phrase
        # ambiguous phrase: no own polarity -> would normally hit context/model
        p = Phrase(surface="คนเยอะ", descriptor_tokens=["คนเยอะ"])
        p.clause = {"clean": "คนเยอะ", "tokens": ["คนเยอะ"], "sentiment": "negative"}
        with mock.patch.object(sentiment, "_predict_model",
                               side_effect=AssertionError("model must not be called")):
            self.assertEqual(sentiment.classify_phrase(p), "negative")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_phrase_sentiment -v`
Expected: FAIL — `_predict_model` is invoked (raises AssertionError) because the current code re-runs the model for ambiguous phrases.

- [ ] **Step 3: Edit `classify_phrase`**

In `core/sentiment.py`, in `classify_phrase`, replace the section starting at `# 2) ambiguous phrase -> decide from clause context` down to the final `return _predict_lexicon(...)` with:

```python
    # 2) ambiguous phrase -> reuse the clause sentiment already computed in
    #    analyze_all (avoids a second, redundant model inference per phrase)
    clause = phrase.clause or {}
    cached = clause.get("sentiment")
    if cached in ("positive", "neutral", "negative"):
        return cached

    # 2b) no cached clause sentiment (e.g. clause-less phrase) -> compute now
    if config.get_use_model():
        try:
            return _predict_model(clause.get("clean", phrase.surface))
        except Exception as e:
            if _model_status != "failed":
                _model_status = "failed"
                print(f"[sentiment] WangchanBERTa unavailable, using lexicon: {e}")
    return _predict_lexicon(clause.get("tokens") or phrase.descriptor_tokens)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_phrase_sentiment -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/sentiment.py tests/test_phrase_sentiment.py
git commit -m "perf(sentiment): reuse clause sentiment for ambiguous phrases"
```

---

### Task 6: Per-review error isolation in `_phrase_pipeline`

**Files:**
- Modify: `core/pipeline.py`
- Test: `tests/test_pipeline_isolation.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_pipeline_isolation.py`:

```python
"""One malformed review/clause must not bring down the whole phrase pipeline."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import pipeline
from core.phrases import extract


class TestPipelineIsolation(unittest.TestCase):
    def test_one_bad_clause_does_not_crash_pipeline(self):
        good = {"clauses": [{"raw_tokens": ["อาหาร", "อร่อย"], "tokens": ["อาหาร", "อร่อย"],
                             "tokens_base": ["อาหาร", "อร่อย"], "sentiment": "positive",
                             "clean": "อาหารอร่อย"}]}
        bad = {"clauses": [{"raw_tokens": ["x"]}]}

        real_extract = extract.extract

        def boom(clause):
            if clause.get("raw_tokens") == ["x"]:
                raise RuntimeError("boom")
            return real_extract(clause)

        with mock.patch.object(extract, "extract", side_effect=boom):
            out = pipeline._phrase_pipeline([bad, good])   # must not raise
        self.assertIn("food", out)   # good review still produced output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_pipeline_isolation -v`
Expected: FAIL with `RuntimeError: boom` propagating out of `_phrase_pipeline`.

- [ ] **Step 3: Rename current logic to `_rule_phrase_pipeline` and wrap per review**

In `core/pipeline.py`, replace the `_phrase_pipeline` function (lines 20-36) with:

```python
def _rule_phrase_pipeline(reviews: list) -> dict:
    collected = []
    for r in reviews:
        try:
            for clause in r.get("clauses", []):
                clause_aspects = aspect.detect_clause_aspects(clause)
                for p in quality.filter_phrases(extract.extract(clause), clause_aspects):
                    canonical.canonicalize(p)
                    synonyms.aggregate(p)
                    if p.aspect is None:                   # not preset by earlier stage
                        a, conf = aspect.route_aspect(p, clause_aspects)
                        p.aspect, p.aspect_conf = a, conf
                    if p.aspect is None:
                        continue
                    p.aspect = _ASPECT_KEY.get(p.aspect, p.aspect)
                    p.sentiment = sentiment.classify_phrase(p)
                    collected.append(p)
        except Exception as e:                             # never let one review 500 the run
            print(f"[phrases] skipped a review due to: {e}")
            continue
    return aggregate.build(collected)


def _phrase_pipeline(reviews: list) -> dict:
    """Engine dispatch lives here in Phase 2; for now always rule-based."""
    return _rule_phrase_pipeline(reviews)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_pipeline_isolation -v`
Expected: PASS

- [ ] **Step 5: Run the full suite (no regressions)**

Run: `python -m unittest discover -s tests -q`
Expected: OK (all tests pass)

- [ ] **Step 6: Commit**

```bash
git add core/pipeline.py tests/test_pipeline_isolation.py
git commit -m "fix(pipeline): isolate per-review failures in phrase pipeline"
```

---

### Task 7: Testable SECRET_KEY resolver with warning

**Files:**
- Modify: `config.py`
- Test: `tests/test_config_secret.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_config_secret.py`:

```python
"""SECRET_KEY falls back to a random per-process key but must warn (multi-worker risk)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


class TestSecretKey(unittest.TestCase):
    def test_env_key_used_as_is_no_warning(self):
        key, used_random = config.resolve_secret_key("my-fixed-key")
        self.assertEqual(key, "my-fixed-key")
        self.assertFalse(used_random)

    def test_blank_env_generates_random_and_flags_warning(self):
        key, used_random = config.resolve_secret_key("")
        self.assertTrue(used_random)
        self.assertGreaterEqual(len(key), 32)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_config_secret -v`
Expected: FAIL with `AttributeError: module 'config' has no attribute 'resolve_secret_key'`

- [ ] **Step 3: Add the resolver and use it**

In `config.py`, replace the `SECRET_KEY = ...` line (line 63) with:

```python
def resolve_secret_key(env_value: str):
    """Return (key, used_random). A blank env value yields a strong per-process
    random key (good enough for this app's flash-only sessions) but the caller
    should warn: under multiple workers each process gets a different key, so set
    SECRET_KEY in production for stable sessions."""
    env_value = (env_value or "").strip()
    if env_value:
        return env_value, False
    return secrets.token_hex(32), True


SECRET_KEY, _SECRET_KEY_IS_RANDOM = resolve_secret_key(os.environ.get("SECRET_KEY", ""))
if _SECRET_KEY_IS_RANDOM:
    print("[config] ⚠️  SECRET_KEY not set — using a random per-process key. "
          "Set SECRET_KEY in production (multi-worker sessions break otherwise).")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_config_secret -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_config_secret.py
git commit -m "fix(config): testable SECRET_KEY resolver with prod warning"
```

---

### Task 8: README — methodology fix, topics, vocab limitation; integration test for `topics`

**Files:**
- Modify: `README.md`
- Test: `tests/test_integration.py` (exists — add a case)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_integration.py` (the `TestPipelineSmoke` class):

```python
    def test_topics_present_and_shaped(self):
        topics = self.result["topics"]
        self.assertEqual(set(topics), {"food", "service", "ambience"})
        for lst in topics.values():
            for item in lst:
                self.assertIn("word", item)
                self.assertIn("count", item)
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `python -m unittest tests.test_integration -v`
Expected: This may already PASS (topics is produced). If it PASSES, keep it as a regression guard and proceed. If it FAILS, fix `run_analysis` to include `topics` (it already does at `core/pipeline.py:72,84`).

- [ ] **Step 3: Update README**

In `README.md`:

1. Find the methodology line stating sentiment is decided **by clause context, not the phrase alone** (around the "แยก การสกัด ออกจาก การตัดสินอารมณ์" bullet). Replace it with text matching the code: *the phrase's own polarity wins; clause context is used only for phrases with no inherent polarity (e.g. `คนเยอะ`).*
2. Add a short subsection documenting the `topics` output ("ลูกค้าพูดถึงบ่อย"): it counts head-noun mentions per aspect, independent of sentiment, for exploration only.
3. Add a "ข้อจำกัด (Limitations)" note: extraction is lexicon-driven, so words absent from `core/lexicon.py` (new slang) are not captured; the lexicon is extended manually.

- [ ] **Step 4: Run the full suite**

Run: `python -m unittest discover -s tests -q`
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add README.md tests/test_integration.py
git commit -m "docs: correct sentiment methodology, document topics + vocab limitation"
```

- [ ] **Step 6: Manual smoke check of live keyword output**

Run:

```bash
python -c "import config; from unittest import mock; \
m1=mock.patch.object(config,'get_apify_token',return_value=''); \
m2=mock.patch.object(config,'get_use_model',return_value=False); m1.start(); m2.start(); \
from core import pipeline; r=pipeline.run_analysis(''); \
import json; open('_kw.txt','w',encoding='utf-8').write(json.dumps(r['keywords'],ensure_ascii=False,indent=2))"
```

Open `_kw.txt`: confirm repeats now aggregate (counts > 1 appear), intensifiers are kept in labels (e.g. `บริการดีมาก`), and no `บริการรอนาน`-style artifacts. Then delete the temp file:

```bash
rm -f _kw.txt
```

**Phase 1 checkpoint:** full suite green; live output visibly improved.

---

# PHASE 2 — Claude (LLM) extraction engine (optional, fallback-guarded)

### Task 9: `extract_engine` user setting

**Files:**
- Modify: `config.py`
- Test: `tests/test_config_engine.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_config_engine.py`:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


class TestExtractEngine(unittest.TestCase):
    def test_default_is_rule(self):
        self.assertEqual(config.get_settings()["extract_engine"], "rule")

    def test_get_extract_engine_helper(self):
        self.assertIn(config.get_extract_engine(), {"rule", "llm"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_config_engine -v`
Expected: FAIL — `KeyError: 'extract_engine'` / no `get_extract_engine`.

- [ ] **Step 3: Edit `config.py`**

In `config.py`:

1. Add to `_DEFAULTS` (after `"use_model": USE_MODEL,`):

```python
    "extract_engine": "rule",     # "rule" (lexicon pipeline) | "llm" (Claude)
```

2. In `get_settings()` return dict, add:

```python
        "extract_engine": (o.get("extract_engine") if o.get("extract_engine") in ("rule", "llm")
                           else _DEFAULTS["extract_engine"]),
```

3. In `save_settings()`, change the allowed set to:

```python
    allowed = {"max_reviews", "use_model", "extract_engine"}
```

4. Add a helper next to `get_use_model`:

```python
def get_extract_engine() -> str:
    return get_settings()["extract_engine"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_config_engine -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_config_engine.py
git commit -m "feat(config): add extract_engine setting (rule|llm)"
```

---

### Task 10: `llm_extract` module — Claude extraction into the contract, with fallback

**Files:**
- Create: `core/phrases/llm_extract.py`
- Test: `tests/test_llm_extract.py` (create)

**Design:** `available()` returns True only when the `anthropic` package imports **and** `ANTHROPIC_API_KEY` is set. `extract_all(reviews)` builds a numbered prompt, asks Claude for structured JSON, maps each item to a `Phrase`, and returns `aggregate.build(phrases)` — the **same contract** as the rule engine. `_client()` is a tiny factory so tests can monkeypatch it without network. No live API calls in tests.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_llm_extract.py`:

```python
"""LLM extraction maps a (mocked) structured response into the dashboard contract,
and reports unavailable when there is no API key. No real API calls are made."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.phrases import llm_extract


class TestLLMExtract(unittest.TestCase):
    def test_unavailable_without_key(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False):
            self.assertFalse(llm_extract.available())

    def test_parse_response_to_contract(self):
        payload = {
            "reviews": [
                {"index": 0, "phrases": [
                    {"phrase": "อาหารแซ่บมาก", "aspect": "food", "sentiment": "positive"},
                    {"phrase": "รอนาน", "aspect": "service", "sentiment": "negative"},
                ]},
                {"index": 1, "phrases": [
                    {"phrase": "รอนาน", "aspect": "service", "sentiment": "negative"},
                ]},
            ]
        }
        contract = llm_extract._to_contract(payload)
        self.assertEqual(contract["food"]["positive"][0]["word"], "อาหารแซ่บมาก")
        neg = contract["service"]["negative"]
        self.assertEqual(neg[0]["word"], "รอนาน")
        self.assertEqual(neg[0]["count"], 2)   # merged across the two reviews

    def test_extract_all_uses_client_and_returns_contract(self):
        payload = {"reviews": [{"index": 0, "phrases": [
            {"phrase": "บริการดีมาก", "aspect": "service", "sentiment": "positive"}]}]}
        fake_msg = mock.Mock()
        fake_block = mock.Mock(); fake_block.type = "text"
        import json
        fake_block.text = json.dumps(payload)
        fake_msg.content = [fake_block]
        fake_client = mock.Mock()
        fake_client.messages.create.return_value = fake_msg
        with mock.patch.object(llm_extract, "_client", return_value=fake_client):
            out = llm_extract.extract_all([{"text": "บริการดีมาก"}])
        self.assertEqual(out["service"]["positive"][0]["word"], "บริการดีมาก")
        fake_client.messages.create.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_llm_extract -v`
Expected: FAIL — `ModuleNotFoundError: core.phrases.llm_extract`.

- [ ] **Step 3: Create the module**

Create `core/phrases/llm_extract.py`:

```python
"""Optional Claude (LLM) extraction engine — an alternative to the rule-based phrase
pipeline. Sends reviews to Claude and asks for structured opinion phrases
(phrase + aspect + sentiment), then maps them into the SAME dashboard contract as
core/phrases/aggregate.build. Imports `anthropic` lazily so the app still runs
without it; callers fall back to the rule engine when available() is False.
"""
import json
import os

from core.phrases.model import Phrase
from core.phrases import aggregate

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")
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
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
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
        model=MODEL,
        max_tokens=_MAX_TOKENS,
        system=_SYSTEM,
        messages=[{"role": "user", "content": _build_prompt(reviews)}],
        output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
    )
    text = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), "")
    payload = json.loads(text)
    return _to_contract(payload)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_llm_extract -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/phrases/llm_extract.py tests/test_llm_extract.py
git commit -m "feat(phrases): optional Claude LLM extraction engine"
```

---

### Task 11: Wire engine dispatch + fallback into the pipeline

**Files:**
- Modify: `core/pipeline.py`
- Test: `tests/test_engine_dispatch.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_engine_dispatch.py`:

```python
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from core import pipeline
from core.phrases import llm_extract


class TestEngineDispatch(unittest.TestCase):
    def test_rule_engine_used_by_default(self):
        with mock.patch.object(config, "get_extract_engine", return_value="rule"), \
             mock.patch.object(llm_extract, "extract_all",
                               side_effect=AssertionError("LLM must not run")):
            pipeline._phrase_pipeline([])   # must not call llm_extract

    def test_llm_engine_falls_back_when_unavailable(self):
        with mock.patch.object(config, "get_extract_engine", return_value="llm"), \
             mock.patch.object(llm_extract, "available", return_value=False), \
             mock.patch.object(pipeline, "_rule_phrase_pipeline",
                               return_value={"food": {}}) as rule:
            out = pipeline._phrase_pipeline([{"clauses": []}])
        rule.assert_called_once()
        self.assertEqual(out, {"food": {}})

    def test_llm_engine_falls_back_on_api_error(self):
        with mock.patch.object(config, "get_extract_engine", return_value="llm"), \
             mock.patch.object(llm_extract, "available", return_value=True), \
             mock.patch.object(llm_extract, "extract_all",
                               side_effect=RuntimeError("api down")), \
             mock.patch.object(pipeline, "_rule_phrase_pipeline",
                               return_value={"food": {}}) as rule:
            out = pipeline._phrase_pipeline([{"clauses": []}])
        rule.assert_called_once()
        self.assertEqual(out, {"food": {}})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_engine_dispatch -v`
Expected: FAIL — current `_phrase_pipeline` ignores the engine setting.

- [ ] **Step 3: Update imports and `_phrase_pipeline`**

In `core/pipeline.py`:

1. Change the import line `from core import scraper, preprocess, sentiment, aspect, keywords, insights` to also import config, and import the llm module:

```python
import config
from core import scraper, preprocess, sentiment, aspect, keywords, insights
from core.phrases import extract, quality, canonical, synonyms, aggregate, llm_extract
```

2. Replace the placeholder `_phrase_pipeline` (created in Task 6) with:

```python
def _phrase_pipeline(reviews: list) -> dict:
    """Dispatch to the configured engine. The LLM engine is opt-in and falls back to
    the rule engine when no API key is available or the API call fails."""
    if config.get_extract_engine() == "llm" and llm_extract.available():
        try:
            return llm_extract.extract_all(reviews)
        except Exception as e:
            print(f"[phrases] LLM engine failed, falling back to rule-based: {e}")
    return _rule_phrase_pipeline(reviews)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_engine_dispatch -v`
Expected: PASS

- [ ] **Step 5: Record which engine ran (for the dashboard/footer)**

In `core/pipeline.py` `run_analysis`, after `kw = _phrase_pipeline(reviews)` (line ~71), add:

```python
    extract_engine = ("llm" if config.get_extract_engine() == "llm" and llm_extract.available()
                      else "rule")
```

and add `"extract_engine": extract_engine,` to the returned dict (next to `"engine":`).

- [ ] **Step 6: Run the full suite**

Run: `python -m unittest discover -s tests -q`
Expected: OK

- [ ] **Step 7: Commit**

```bash
git add core/pipeline.py tests/test_engine_dispatch.py
git commit -m "feat(pipeline): engine dispatch with automatic LLM->rule fallback"
```

---

### Task 12: Settings UI toggle + requirements + README for the LLM engine

**Files:**
- Modify: `templates/settings.html`
- Modify: `app.py` (`save_settings` route)
- Modify: `requirements.txt`
- Modify: `README.md`
- Test: `tests/test_save_settings_route.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_save_settings_route.py`:

```python
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


class TestSaveSettingsEngine(unittest.TestCase):
    def test_extract_engine_is_persisted(self):
        captured = {}
        with mock.patch.object(config, "save_settings",
                               side_effect=lambda c: captured.update(c)):
            import app
            client = app.app.test_client()
            client.post("/settings", data={"engine": "lexicon",
                                           "extract_engine": "llm",
                                           "max_reviews": "20"})
        self.assertEqual(captured.get("extract_engine"), "llm")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_save_settings_route -v`
Expected: FAIL — the route does not read `extract_engine` yet.

- [ ] **Step 3: Update the `save_settings` route**

In `app.py`, in `save_settings()`, after the `changes = {"use_model": ...}` line add:

```python
    engine = request.form.get("extract_engine")
    if engine in ("rule", "llm"):
        changes["extract_engine"] = engine
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_save_settings_route -v`
Expected: PASS

- [ ] **Step 5: Add the UI control**

In `templates/settings.html`, after the existing engine radio-cards block (the `use_model` group ending around line 40), add a second group (the `settings()` route already passes `s=config.get_settings()`, which now contains `extract_engine`):

```html
      <h3 class="set-h">วิธีสกัดวลีคำสำคัญ</h3>
      <div class="radio-cards">
        <label class="radio-card {{ 'sel' if s.extract_engine == 'rule' }}">
          <input type="radio" name="extract_engine" value="rule" {{ 'checked' if s.extract_engine == 'rule' }}>
          <span class="rc-title">Rule-based (พจนานุกรม)</span>
          <span class="rc-sub">ทำงานออฟไลน์ ไม่มีค่าใช้จ่าย โปร่งใส อธิบายได้</span>
        </label>
        <label class="radio-card {{ 'sel' if s.extract_engine == 'llm' }}">
          <input type="radio" name="extract_engine" value="llm" {{ 'checked' if s.extract_engine == 'llm' }}>
          <span class="rc-title">Claude (LLM)</span>
          <span class="rc-sub">แม่นกว่าในรีวิวภาษาธรรมชาติ — ต้องตั้ง ANTHROPIC_API_KEY (ถ้าไม่มีจะใช้ rule-based อัตโนมัติ)</span>
        </label>
      </div>
```

> Match the exact class names used by the existing radio-cards in this file (`rc-title`/`rc-sub` may differ — copy the inner markup of the existing `use_model` cards so styling is consistent).

- [ ] **Step 6: Add the optional dependency**

In `requirements.txt`, add a line:

```
anthropic>=0.40    # optional — only needed for the Claude (LLM) extraction engine
```

- [ ] **Step 7: Document in README**

In `README.md`, add a short "เครื่องยนต์สกัดวลี (Extraction engines)" section: rule-based (default, offline) vs Claude (opt-in). State the env vars (`ANTHROPIC_API_KEY`, optional `ANTHROPIC_MODEL`, default `claude-opus-4-8`, with `claude-haiku-4-5` as the low-cost option), the automatic fallback, and the rough per-analysis cost.

- [ ] **Step 8: Run the full suite**

Run: `python -m unittest discover -s tests -q`
Expected: OK

- [ ] **Step 9: Commit**

```bash
git add templates/settings.html app.py requirements.txt README.md tests/test_save_settings_route.py
git commit -m "feat(settings): expose extraction-engine toggle; document Claude engine"
```

---

# PHASE 3 — Engine comparison (academic deliverable)

### Task 13: `compare_engines.py` — rule vs LLM metrics

**Files:**
- Create: `scripts/compare_engines.py`
- Test: `tests/test_compare_engines.py` (create)

**Design:** a headless function `compare(reviews, run_llm=False)` that runs the rule engine (always) and the LLM engine (only when `run_llm` and `llm_extract.available()`), then computes simple comparison metrics: phrase counts per engine and per-aspect overlap of produced phrase strings. The CLI prints a table; tests call `compare(...)` with `run_llm=False` so no API key/network is needed.

- [ ] **Step 1: Write the failing test**

Create `tests/test_compare_engines.py`:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import compare_engines


class TestCompareEngines(unittest.TestCase):
    def test_rule_only_comparison_runs_headless(self):
        reviews = [
            {"text": "อาหารอร่อยมาก แต่บริการช้า"},
            {"text": "พนักงานน่ารัก รอนาน"},
        ]
        report = compare_engines.compare(reviews, run_llm=False)
        self.assertIn("rule", report)
        self.assertIn("llm", report)
        self.assertIsNone(report["llm"])              # skipped without key
        self.assertGreaterEqual(report["rule"]["total_phrases"], 1)
        self.assertIn("food", report["rule"]["per_aspect"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_compare_engines -v`
Expected: FAIL — `ModuleNotFoundError: scripts.compare_engines`.

- [ ] **Step 3: Create the script (and make `scripts/` a package)**

Create empty `scripts/__init__.py`:

```python
```

Create `scripts/compare_engines.py`:

```python
"""Compare the rule-based and Claude (LLM) extraction engines on the same reviews.

Rule-based always runs (offline). The LLM half runs only with run_llm=True AND a
configured ANTHROPIC_API_KEY; otherwise it is reported as skipped. This is the
evidence for the rule-vs-LLM comparison in the write-up.

CLI:  python -m scripts.compare_engines [--llm]
      (uses data/labeled_reviews.json when present, else the demo sample)
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from core import preprocess, sentiment, aspect
from core.phrases import llm_extract
from core import pipeline


def _summarize(contract: dict) -> dict:
    per_aspect, total = {}, 0
    for a, by_sent in contract.items():
        words = []
        for items in by_sent.values():
            words += [it["word"] for it in items]
        per_aspect[a] = words
        total += len(words)
    return {"total_phrases": total, "per_aspect": per_aspect}


def _run_rule(reviews: list) -> dict:
    prepared = preprocess.filter_and_prepare(reviews)
    prepared = sentiment.analyze_all(prepared)
    prepared = aspect.tag_aspects(prepared)
    return _summarize(pipeline._rule_phrase_pipeline(prepared))


def compare(reviews: list, run_llm: bool = False) -> dict:
    report = {"rule": _run_rule(reviews), "llm": None}
    if run_llm and llm_extract.available():
        try:
            report["llm"] = _summarize(llm_extract.extract_all(reviews))
        except Exception as e:
            report["llm"] = {"error": str(e)}
    return report


def _load_reviews() -> list:
    path = os.path.join(config.DATA_DIR, "labeled_reviews.json")
    if not os.path.exists(path):
        path = os.path.join(config.DATA_DIR, "sample_reviews.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["reviews"] if isinstance(data, dict) else data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true", help="also run the Claude engine")
    args = ap.parse_args()
    report = compare(_load_reviews(), run_llm=args.llm)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_compare_engines -v`
Expected: PASS

- [ ] **Step 5: Run the full suite**

Run: `python -m unittest discover -s tests -q`
Expected: OK

- [ ] **Step 6: Commit**

```bash
git add scripts/__init__.py scripts/compare_engines.py tests/test_compare_engines.py
git commit -m "feat(scripts): rule-vs-LLM engine comparison harness"
```

---

## Final verification

- [ ] Run the complete suite once more:

Run: `python -m unittest discover -s tests -q`
Expected: `OK` with the original 110 tests plus the new ones, zero failures.

- [ ] Confirm default behavior unchanged: with no `ANTHROPIC_API_KEY` and default settings, `run_analysis` uses the rule engine and the dashboard renders (the four uncommitted working-tree files — `config.py`, `templates/dashboard.html`, `static/js/dashboard.js`, `static/css/style.css` — should be committed as part of their respective tasks where touched, or in a dedicated commit if still pending).

---

## Self-Review notes (author)

- **Spec coverage:** Phase 1 §4 → Tasks 1–8; Phase 2 §5 → Tasks 9–12; Phase 3 §6 → Task 13; review fixes §4.5 → Tasks 5,6,7,8. All spec sections map to a task.
- **Contract stability:** both engines return the `aggregate.build` shape; `insights.py`, `db/database.py`, template unchanged.
- **Type consistency:** `Phrase.display`/`Phrase.agg_key` (Task 1) are produced in `canonical.py`/`synonyms.py` (Tasks 2–3) and consumed in `aggregate.py` (Task 3) and `llm_extract.py` (Task 10) with the same names; `available()`/`extract_all()`/`_to_contract()`/`_client()` names match across Tasks 10–13.
- **No live API in tests:** Tasks 10, 11, 13 mock the SDK/availability; only `available()` reads the env.
```
