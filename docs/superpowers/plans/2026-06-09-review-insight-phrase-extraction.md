# Review Insight — Phrase Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-word/weak-bigram keyword stage with a deterministic, explainable pipeline that extracts canonical Thai opinion phrases and classifies each by aspect (Food/Service/Atmosphere) and sentiment (pos/neu/neg).

**Architecture:** POS-pattern chunking + lexicon validation (Architecture 2). Per-clause hybrid extraction (idiom dict → POS grammar → lexicon fallback), then quality filtering, canonicalization, conservative synonym aggregation, a 4-tier aspect resolver, context-based sentiment (reusing WangchanBERTa), and count aggregation. Each stage is a pure function over a `Phrase` object, unit-testable with **injected POS tags**.

**Tech Stack:** Python 3.12, PyThaiNLP (already installed), WangchanBERTa via transformers (optional), `unittest` (no pytest in this repo).

**Spec:** `docs/superpowers/specs/2026-06-09-review-insight-phrase-extraction-design.md`

**Test convention:** run a single test module with
`python -m unittest tests.test_<name> -v` and the full suite with
`python -m unittest discover -s tests -v`.

---

## ⚠️ DESIGN CHANGE (after Task 2) — Lexicon-driven extraction; POS dropped

Task 2 empirically confirmed (across `orchid`, `orchid_ud`, `pud` engines) that the
installed PyThaiNLP mis-tags Thai opinion words: `อร่อย`→NOUN, `ดี`→ADV, `รวดเร็ว`→ADV,
`จัดจ้าน`→NOUN, `เข้มข้น`→ADV. POS tagging is therefore **not reliable** for slot-typing.
Per user decision (Option A), **POS is removed from extraction; the curated lexicon is
authoritative.** `core/postag.py` + `tests/test_postag.py` are deleted. The POS
evaluation becomes a documented thesis finding (README Task 16).

**Revised slot predicates** (in `core/phrases/extract.py`; no POS, plain token lists —
not `(tok, tag)` pairs):
```python
def is_noun(tok):   return tok in NOUN_TO_ASPECT
def is_desc(tok):   return negation.word_polarity(tok) != 0 or tok in DESCRIPTOR_ASPECT_HINTS
def is_neg(tok):    return tok in negation.NEGATORS or tok.startswith("ไม่")
def is_filler(tok): return tok in FILLERS
```

**Revised extraction strategies** (per clause, overlap-suppressed):
- **A. Idiom MWE** longest-match (Task 6, unchanged).
- **B. Lexicon grammar** (Task 7), single left-to-right pass:
  - **B1 lexicon-phrase recovery:** adjacent `a b` where `(a+b)` is a single polar
    lexicon entry and `b` alone is not a descriptor → phrase (`รอ`+`นาน`→`รอนาน`,
    pattern `P3`). `head_noun = a if is_noun(a) else None`.
  - **B2 noun-led:** `NOUN (NEG)? descriptor-run(+intensifiers)` → `P1`/`P2`.
  - **B3 standalone descriptor / compound** → `P7`.
- The separate POS-off "fallback" strategy from the original Task 8 is **removed** — B
  is already lexicon-only. Task 8 becomes just the public `extract()` orchestrator.

**Authoritative revised `core/phrases/extract.py`** (Tasks 6–8 build up to this):
```python
"""Stage 1 — lexicon-driven phrase extraction (idiom dict → lexicon grammar).
POS was evaluated and found unreliable on Thai review text (see README); the curated
lexicon is authoritative. Each strategy suppresses tokens consumed by earlier ones."""
from core import negation
from core.lexicon import (
    NOUN_TO_ASPECT, DESCRIPTOR_ASPECT_HINTS, IDIOMS, INTENSIFIERS, FILLERS,
    SENTIMENT_WORDS,
)
from core.phrases.model import Phrase

_POLAR = set(SENTIMENT_WORDS["positive"]) | set(SENTIMENT_WORDS["negative"])
_MAX_IDIOM_SPAN = 4


def _match_idioms(raw, clause):
    used = [False] * len(raw)
    out, i, n = [], 0, len(raw)
    while i < n:
        matched = False
        for span in range(min(_MAX_IDIOM_SPAN, n - i), 0, -1):
            glued = "".join(raw[i:i + span])
            if glued in IDIOMS:
                out.append(Phrase(surface=glued, pattern="idiom", clause=clause))
                for k in range(i, i + span):
                    used[k] = True
                i += span; matched = True; break
        if not matched:
            i += 1
    return out, used


def is_noun(tok):   return tok in NOUN_TO_ASPECT
def is_desc(tok):   return negation.word_polarity(tok) != 0 or tok in DESCRIPTOR_ASPECT_HINTS
def is_neg(tok):    return tok in negation.NEGATORS or tok.startswith("ไม่")
def is_filler(tok): return tok in FILLERS


def _collect_descriptor_run(raw, j, n):
    """From index j: collect descriptor tokens, skipping fillers, excluding
    intensifiers. Returns (descriptor_tokens, end_index)."""
    desc = []
    while j < n:
        tok = raw[j]
        if tok in INTENSIFIERS or is_filler(tok):
            j += 1; continue
        if is_desc(tok):
            desc.append(tok); j += 1; continue
        break
    return desc, j


def _match_grammar(raw, used, clause):
    out, i, n = [], 0, len(raw)
    while i < n:
        if used[i]:
            i += 1; continue
        a = raw[i]
        b = raw[i + 1] if i + 1 < n else None

        # B1 lexicon-phrase recovery (รอ+นาน -> "รอนาน")
        if (b is not None and not used[i + 1] and (a + b) in _POLAR and not is_desc(b)):
            if is_noun(a):
                head, dtoks = a, [b]
            else:
                head, dtoks = None, [a + b]
            out.append(Phrase(surface=f"{a} {b}", head_noun=head,
                              descriptor_tokens=dtoks, pattern="P3", clause=clause))
            used[i] = used[i + 1] = True
            i += 2; continue

        # B2 noun-led: NOUN (NEG)? descriptor-run
        if is_noun(a):
            j = i + 1
            neg = []
            if j < n and is_neg(raw[j]) and j + 1 < n and is_desc(raw[j + 1]):
                neg = [raw[j]]; j += 1
            desc, j2 = _collect_descriptor_run(raw, j, n)
            if desc:
                out.append(Phrase(surface=" ".join(raw[i:j2]), head_noun=a,
                                  descriptor_tokens=neg + desc,
                                  pattern="P2" if neg else "P1", clause=clause))
                for k in range(i, j2):
                    used[k] = True
                i = j2; continue

        # B3 standalone descriptor / compound -> P7
        if is_desc(a):
            desc, j2 = _collect_descriptor_run(raw, i, n)
            if desc:
                out.append(Phrase(surface=" ".join(raw[i:j2]), head_noun=None,
                                  descriptor_tokens=desc, pattern="P7", clause=clause))
                for k in range(i, j2):
                    used[k] = True
                i = j2; continue

        i += 1
    return out


def extract(clause: dict) -> list:
    """Public Stage-1 entry point. clause must have 'raw_tokens'."""
    raw = clause.get("raw_tokens") or []
    if not raw:
        return []
    phrases, used = _match_idioms(raw, clause)
    phrases += _match_grammar(raw, used, clause)
    return phrases
```

Tests for Tasks 6–8 use **plain token lists** (no tag injection). Task 3 lexicon is
enriched with common review descriptors. Task 15 wiring drops the `postag` import.
Known limitation (document in README): split verb+noun+descriptor like `รออาหารนาน`
is not recovered (only the adjacent `รอนาน` form is).

---

## File Structure

| File | Responsibility |
|---|---|
| `core/phrases/__init__.py` | package marker (empty) |
| `core/phrases/model.py` | `Phrase` dataclass (the object flowing through stages) |
| `core/postag.py` | PyThaiNLP POS wrapper + tag-set constants; graceful fallback |
| `core/lexicon.py` *(modify)* | add `NOUN_TO_ASPECT`, `ASPECT_HEAD_NOUN`, `IDIOMS`, `DESCRIPTOR_ASPECT_HINTS`, `INTENSIFIERS`, `FILLERS`, `META_VERBS`, `SYNONYM_GROUPS` (+ reverse maps) |
| `core/clause.py` *(modify)* | add `split_clause_tokens()` (token-level; fixes `ตกแต่ง` bug) |
| `core/preprocess.py` *(modify)* | clause split on tokens; add `raw_tokens` to each clause |
| `core/phrases/extract.py` | Stage 1: hybrid extraction (idiom/POS/fallback) → `list[Phrase]` |
| `core/phrases/quality.py` | Stage 2: reject bad phrases; set provisional aspect + confidence for P7 |
| `core/phrases/canonical.py` | Stage 3: build canonical string; gated head-noun synthesis |
| `core/phrases/synonyms.py` | Stage 4: conservative concept aggregation |
| `core/aspect.py` *(modify)* | Stage 5: `detect_clause_aspects()` + `route_aspect()` (4-tier) |
| `core/sentiment.py` *(modify)* | Stage 6: `classify_phrase()` (context-based) |
| `core/phrases/aggregate.py` | Stage 7: count by (aspect, sentiment, concept) → dashboard contract |
| `core/pipeline.py` *(modify)* | wire stages; keep output keys unchanged |
| `README.md` *(modify)* | document the new pipeline (final task) |

`core/keyphrase.py` and the keyword-bucketing in `core/keywords.py` are superseded;
`keywords.extract_topics` is reused. Removal happens only after parity (Task 16).

---

## Task 1: Phrase model + phrases package

**Files:**
- Create: `core/phrases/__init__.py`
- Create: `core/phrases/model.py`
- Test: `tests/test_phrase_model.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_phrase_model.py
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.phrases.model import Phrase


class TestPhraseModel(unittest.TestCase):
    def test_defaults(self):
        p = Phrase(surface="อาหาร อร่อย")
        self.assertEqual(p.surface, "อาหาร อร่อย")
        self.assertIsNone(p.head_noun)
        self.assertEqual(p.descriptor_tokens, [])
        self.assertEqual(p.aspect_conf, "low")
        self.assertEqual(p.clause, {})

    def test_independent_mutable_defaults(self):
        a, b = Phrase(surface="x"), Phrase(surface="y")
        a.descriptor_tokens.append("อร่อย")
        self.assertEqual(b.descriptor_tokens, [])  # no shared mutable default


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_phrase_model -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.phrases'`

- [ ] **Step 3: Write minimal implementation**

```python
# core/phrases/__init__.py
```

```python
# core/phrases/model.py
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
    concept: str = ""                             # stage 4 concept key (== canonical if ungrouped)
    label: str = ""                               # display label
    aspect: str | None = None                     # food | service | atmosphere
    aspect_conf: str = "low"                      # "high" | "medium" | "low"
    sentiment: str | None = None                  # positive | neutral | negative (stage 6)
    clause: dict = field(default_factory=dict)    # source clause for context sentiment
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_phrase_model -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add core/phrases/__init__.py core/phrases/model.py tests/test_phrase_model.py
git commit -m "feat: add Phrase data model for Review Insight pipeline"
```

---

## Task 2: POS-tag wrapper (`core/postag.py`)

**Files:**
- Create: `core/postag.py`
- Test: `tests/test_postag.py`

> The wrapper isolates PyThaiNLP so every later module can be tested with injected
> tags. Tag-set constants are defined here. **During execution, confirm the actual
> tags your PyThaiNLP version emits** (print `pos_tag(["อร่อย","สด","ดี"])`) and adjust
> the constant sets if needed — the grammar also validates against the lexicon, so it
> degrades safely even if a tag is missing.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_postag.py
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import postag


class TestPostag(unittest.TestCase):
    def test_returns_pairs_for_each_token(self):
        out = postag.pos_tag(["อาหาร", "อร่อย"])
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0][0], "อาหาร")
        self.assertTrue(isinstance(out[0][1], str))

    def test_empty_input(self):
        self.assertEqual(postag.pos_tag([]), [])

    def test_available_is_bool(self):
        self.assertIn(postag.available(), (True, False))

    def test_tagsets_exist(self):
        self.assertIn("NOUN", postag.NOUN_TAGS)
        self.assertTrue(postag.STATIVE_TAGS)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_postag -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.postag'`

- [ ] **Step 3: Write minimal implementation**

```python
# core/postag.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_postag -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add core/postag.py tests/test_postag.py
git commit -m "feat: add PyThaiNLP POS wrapper with graceful fallback"
```

---

## Task 3: Expand the lexicon (`core/lexicon.py`)

**Files:**
- Modify: `core/lexicon.py` (append; keep existing `ASPECT_LEXICON`, `SENTIMENT_WORDS`, `ASPECT_LABELS_TH` untouched for back-compat)
- Test: `tests/test_lexicon_maps.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_lexicon_maps.py
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import lexicon


class TestLexiconMaps(unittest.TestCase):
    def test_noun_to_aspect(self):
        self.assertEqual(lexicon.NOUN_TO_ASPECT["ราคา"], "food")   # Price-into-Food
        self.assertEqual(lexicon.NOUN_TO_ASPECT["พนักงาน"], "service")
        self.assertEqual(lexicon.NOUN_TO_ASPECT["บรรยากาศ"], "atmosphere")

    def test_aspect_head_noun(self):
        self.assertEqual(lexicon.ASPECT_HEAD_NOUN["food"], "อาหาร")
        self.assertEqual(set(lexicon.ASPECT_HEAD_NOUN), {"food", "service", "atmosphere"})

    def test_idioms(self):
        self.assertEqual(lexicon.IDIOMS["ติดริมน้ำ"]["aspect"], "atmosphere")
        self.assertIn("canonical", lexicon.IDIOMS["ถึงเครื่อง"])

    def test_descriptor_hints(self):
        self.assertEqual(lexicon.DESCRIPTOR_ASPECT_HINTS["อร่อย"], "food")
        self.assertEqual(lexicon.DESCRIPTOR_ASPECT_HINTS["คึกคัก"], "atmosphere")

    def test_strip_sets(self):
        self.assertIn("มากๆ", lexicon.INTENSIFIERS)
        self.assertIn("คือ", lexicon.FILLERS)
        self.assertIn("แนะนำ", lexicon.META_VERBS)

    def test_synonym_groups_and_reverse(self):
        self.assertIn("ราคาไม่แพง", lexicon.SYNONYM_GROUPS["price_good"]["members"])
        key, label, aspect = lexicon.MEMBER_TO_CONCEPT["คุ้มค่า"]
        self.assertEqual((key, aspect), ("price_good", "food"))
        # antonyms stay separate
        self.assertNotEqual(
            lexicon.MEMBER_TO_CONCEPT["ราคาแพง"][0],
            lexicon.MEMBER_TO_CONCEPT["ราคาไม่แพง"][0],
        )

    def test_distinct_descriptors_not_grouped(self):
        for w in ("อร่อย", "จัดจ้าน", "เข้มข้น", "ถึงเครื่อง"):
            self.assertNotIn(w, lexicon.MEMBER_TO_CONCEPT)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_lexicon_maps -v`
Expected: FAIL — `AttributeError: module 'core.lexicon' has no attribute 'NOUN_TO_ASPECT'`

- [ ] **Step 3: Write minimal implementation**

Append to `core/lexicon.py`:

```python
# ---------------------------------------------------------------------------
# 3) Phrase-extraction maps (Review Insight pipeline)
# ---------------------------------------------------------------------------

# Head nouns per aspect (pure topic markers — NO polarity words here).
# Note: ราคา routes to "food" per the Price-into-Food product decision.
ASPECT_NOUNS = {
    "food": {
        "อาหาร", "เมนู", "เมนูอาหาร", "รสชาติ", "รส", "วัตถุดิบ", "จาน", "ปริมาณ",
        "ของหวาน", "เครื่องดื่ม", "เนื้อ", "ข้าว", "น้ำจิ้ม", "ซุป", "ของกิน",
        "กับข้าว", "ชิ้น", "คำ", "เครื่องปรุง", "ปลา", "ราคา",
    },
    "service": {
        "บริการ", "พนักงาน", "เสิร์ฟ", "คิว", "ออเดอร์", "คิดเงิน", "จ่ายเงิน",
        "พนง", "เด็กเสิร์ฟ", "บริกร", "ต้อนรับ",
    },
    "atmosphere": {
        "บรรยากาศ", "แอร์", "ที่จอดรถ", "ห้องน้ำ", "โต๊ะ", "เก้าอี้", "วิว", "มุม",
        "ร้าน", "เพลง", "แสง", "คน",
    },
}

NOUN_TO_ASPECT = {n: a for a, nouns in ASPECT_NOUNS.items() for n in nouns}

ASPECT_HEAD_NOUN = {"food": "อาหาร", "service": "บริการ", "atmosphere": "บรรยากาศ"}

# Multi-word expressions POS can't parse. Key == joined idiom string (no spaces).
IDIOMS = {
    "ติดริมน้ำ": {"canonical": "ติดริมน้ำ", "aspect": "atmosphere"},
    "ริมน้ำ":    {"canonical": "ติดริมน้ำ", "aspect": "atmosphere"},
    "ถึงเครื่อง": {"canonical": "ถึงเครื่อง", "aspect": "food"},
    "มาไว":      {"canonical": "มาไว", "aspect": "service"},
}

# Descriptor → aspect. Used both to (a) detect clause aspects and (b) route
# noun-less phrases (tier 4) and bare-descriptor synthesis (provisional aspect).
DESCRIPTOR_ASPECT_HINTS = {
    # food-bound descriptors
    "อร่อย": "food", "จืด": "food", "เค็ม": "food", "หวาน": "food", "เปรี้ยว": "food",
    "เผ็ด": "food", "สด": "food", "หอม": "food", "เข้มข้น": "food", "จัดจ้าน": "food",
    "นุ่ม": "food", "กรอบ": "food",
    # service-bound descriptors
    "รวดเร็ว": "service", "ช้า": "service", "ใส่ใจ": "service", "ยิ้มแย้ม": "service",
    "หยาบคาย": "service",
    # atmosphere-bound descriptors (incl. noun-less compounds)
    "สวย": "atmosphere", "สะอาด": "atmosphere", "สกปรก": "atmosphere",
    "เย็นสบาย": "atmosphere", "คึกคัก": "atmosphere", "เงียบสงบ": "atmosphere",
    "โล่ง": "atmosphere", "อึดอัด": "atmosphere", "โทรม": "atmosphere",
}

INTENSIFIERS = {"มาก", "มากๆ", "สุดๆ", "จริง", "จริงๆ", "เลย", "ๆ", "ที่สุด", "นิดหน่อย"}
FILLERS = {"คือ", "ที่", "อะ", "นะ", "ก็"}
META_VERBS = {"ชอบ", "แนะนำ", "บอก", "คิดว่า", "รู้สึก"}

# ---------------------------------------------------------------------------
# 4) Conservative synonym aggregation (opt-in whitelist; default = identity)
#    Merge ONLY when: same business lever + same orientation + manager acts
#    identically. Distinct sensory descriptors are NOT merged.
# ---------------------------------------------------------------------------
SYNONYM_GROUPS = {
    "price_good": {"label": "ราคาคุ้มค่า", "aspect": "food",
                   "members": {"คุ้มค่า", "ราคาดี", "ราคาไม่แพง", "ราคาเหมาะสม", "ราคาโอเค"}},
    "price_bad":  {"label": "ราคาแพง", "aspect": "food",
                   "members": {"ราคาแพง", "แพงไป", "ไม่คุ้ม", "ไม่คุ้มค่า"}},
    "wait_long":  {"label": "รอนาน", "aspect": "service",
                   "members": {"รอนาน", "มาช้า", "อาหารมาช้า", "เสิร์ฟช้า"}},
    "taste_good": {"label": "รสชาติดี", "aspect": "food",
                   "members": {"รสชาติดี", "รสดี"}},
}

# reverse map: member phrase -> (concept_key, label, aspect)
MEMBER_TO_CONCEPT = {
    m: (key, g["label"], g["aspect"])
    for key, g in SYNONYM_GROUPS.items()
    for m in g["members"]
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_lexicon_maps -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add core/lexicon.py tests/test_lexicon_maps.py
git commit -m "feat: add phrase-extraction lexicon maps (nouns, idioms, hints, synonyms)"
```

---

## Task 4: Clause split on tokens (`core/clause.py`)

Fixes the confirmed bug where the raw-substring split mangles `ตกแต่ง`/`แต่เช้า`.

**Files:**
- Modify: `core/clause.py` (add `split_clause_tokens`; keep `split_clauses` for back-compat)
- Test: `tests/test_clause.py` (extend existing)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_clause.py`:

```python
class TestSplitClauseTokens(unittest.TestCase):
    def test_splits_on_marker_token_only(self):
        from core.clause import split_clause_tokens
        toks = ["อาหาร", "อร่อย", "แต่", "บริการ", "ช้า"]
        self.assertEqual(
            split_clause_tokens(toks),
            [["อาหาร", "อร่อย"], ["บริการ", "ช้า"]],
        )

    def test_does_not_split_word_containing_marker(self):
        from core.clause import split_clause_tokens
        # "ตกแต่ง" is one token; must NOT be split even though it contains "แต่"
        toks = ["ร้าน", "ตกแต่ง", "สวย"]
        self.assertEqual(split_clause_tokens(toks), [["ร้าน", "ตกแต่ง", "สวย"]])

    def test_empty_returns_empty(self):
        from core.clause import split_clause_tokens
        self.assertEqual(split_clause_tokens([]), [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_clause -v`
Expected: FAIL — `ImportError: cannot import name 'split_clause_tokens'`

- [ ] **Step 3: Write minimal implementation**

Append to `core/clause.py`:

```python
# Marker tokens (token-level split — avoids the substring bug that mangled "ตกแต่ง")
_MARKER_TOKENS = {"แต่", "แต่ว่า", "อย่างไรก็ตาม"}


def split_clause_tokens(tokens: list) -> list:
    """Split a token list into clauses on contrastive marker *tokens* only.

    Operates on already-tokenized input, so "แต่" inside a word like "ตกแต่ง"
    (which the tokenizer keeps whole) is never treated as a boundary.
    Returns list[list[str]]; empty input -> [].
    """
    if not tokens:
        return []
    clauses, cur = [], []
    for t in tokens:
        if t in _MARKER_TOKENS:
            if cur:
                clauses.append(cur)
                cur = []
        else:
            cur.append(t)
    if cur:
        clauses.append(cur)
    return clauses or [list(tokens)]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_clause -v`
Expected: PASS (existing tests + 3 new)

- [ ] **Step 5: Commit**

```bash
git add core/clause.py tests/test_clause.py
git commit -m "fix: split clauses on tokens to avoid mangling words containing แต่"
```

---

## Task 5: Preprocess provides `raw_tokens` and token-level clauses (`core/preprocess.py`)

Each clause must carry `raw_tokens` (full tokenization, no stopword removal) so the
extractor can POS-tag and run the grammar; `tokens`/`tokens_base` are kept for the
sentiment backstop and topics.

**Files:**
- Modify: `core/preprocess.py` (`_prepare_clauses`, `filter_and_prepare`, `preprocess_review`)
- Test: `tests/test_preprocess.py` (extend existing)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_preprocess.py`:

```python
class TestRawTokensAndClauseSplit(unittest.TestCase):
    def test_clause_has_raw_tokens(self):
        from core import preprocess
        out = preprocess.filter_and_prepare(
            [{"text": "อาหารอร่อยมาก แต่ บริการช้า", "rating": 5, "review_date": None}]
        )
        self.assertEqual(len(out), 1)
        clauses = out[0]["clauses"]
        self.assertGreaterEqual(len(clauses), 2)
        for c in clauses:
            self.assertIn("raw_tokens", c)
            self.assertTrue(all(isinstance(t, str) for t in c["raw_tokens"]))

    def test_raw_tokens_keep_function_words(self):
        from core import preprocess
        out = preprocess.preprocess_review("ราคาไม่แพง")
        self.assertIn("raw_tokens", out)
        # negation word retained in raw_tokens (not stopword-stripped)
        self.assertIn("ไม่", out["raw_tokens"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_preprocess -v`
Expected: FAIL — `KeyError: 'raw_tokens'`

- [ ] **Step 3: Write minimal implementation**

In `core/preprocess.py`, add `raw_tokens` to `preprocess_review` and rewrite the
clause builder to split on tokens. Replace the body of `preprocess_review` and
`_prepare_clauses`:

```python
def preprocess_review(text: str) -> dict:
    """Prepare one review/clause string.

    Returns clean text + three token views:
      tokens       : negation-merged, stopword-removed (sentiment backstop, fallback)
      tokens_base  : stopword-removed, no negation merge (topics)
      raw_tokens   : full tokenization, NO stopword removal (extraction + POS)
    """
    cleaned = clean_text(text)
    raw = tokenize(cleaned)
    tokens = remove_stopwords(negation.apply_negation(raw))
    tokens_base = remove_stopwords(raw)
    return {
        "clean": cleaned,
        "tokens": tokens,
        "tokens_base": tokens_base,
        "raw_tokens": raw,
    }


def _prepare_clauses(text: str) -> list:
    """Tokenize the whole cleaned review once, split on marker *tokens*, then build
    per-clause token views. Avoids double-tokenization and the substring split bug."""
    cleaned = clean_text(text)
    raw = tokenize(cleaned)
    clauses = []
    for raw_clause in clause.split_clause_tokens(raw):
        if not raw_clause:
            continue
        clauses.append({
            "clean": "".join(raw_clause),
            "tokens": remove_stopwords(negation.apply_negation(raw_clause)),
            "tokens_base": remove_stopwords(raw_clause),
            "raw_tokens": raw_clause,
        })
    return clauses
```

`filter_and_prepare` already calls `_prepare_clauses(text)` and falls back to a single
clause when empty — update that fallback block to include `raw_tokens`:

```python
        clauses = _prepare_clauses(text)
        if not clauses:                  # guard: never lose a review
            clauses = [{
                "clean": pp["clean"],
                "tokens": pp["tokens"],
                "tokens_base": pp["tokens_base"],
                "raw_tokens": pp["raw_tokens"],
            }]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_preprocess -v`
Expected: PASS (existing + 2 new)

- [ ] **Step 5: Run the existing clause-pipeline test to confirm no regression**

Run: `python -m unittest tests.test_clause_pipeline -v`
Expected: PASS (clause dicts still have tokens/tokens_base; new `raw_tokens` is additive)

- [ ] **Step 6: Commit**

```bash
git add core/preprocess.py tests/test_preprocess.py
git commit -m "feat: add raw_tokens and token-level clause split to preprocess"
```

---

## Task 6: Extraction — idiom strategy (`core/phrases/extract.py`)

**Files:**
- Create: `core/phrases/extract.py`
- Test: `tests/test_extract_idiom.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_extract_idiom.py
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.phrases import extract


class TestIdiomMatch(unittest.TestCase):
    def test_matches_multitoken_idiom(self):
        # tokenizer split: ["ติด","ริมน้ำ"] -> idiom "ติดริมน้ำ"
        phrases, used = extract._match_idioms(["ติด", "ริมน้ำ"], {})
        keys = [p.surface for p in phrases]
        self.assertIn("ติดริมน้ำ", keys)
        self.assertTrue(all(used))
        self.assertEqual(phrases[0].pattern, "idiom")

    def test_no_idiom_returns_empty(self):
        phrases, used = extract._match_idioms(["อาหาร", "อร่อย"], {})
        self.assertEqual(phrases, [])
        self.assertEqual(used, [False, False])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_extract_idiom -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.phrases.extract'`

- [ ] **Step 3: Write minimal implementation**

```python
# core/phrases/extract.py
"""Stage 1 — hybrid phrase extraction (idiom dict → POS grammar → lexicon fallback).

Each strategy returns (list[Phrase], used_flags). A token consumed by an earlier
strategy is not reused (overlap suppression). All slot tests validate against the
lexicon so the grammar degrades safely when POS tags are missing/UNK.
"""
from core import postag, negation
from core.lexicon import (
    NOUN_TO_ASPECT, DESCRIPTOR_ASPECT_HINTS, IDIOMS, INTENSIFIERS, FILLERS,
)
from core.phrases.model import Phrase

# longest idiom first so multi-token idioms win over their substrings
_IDIOM_KEYS = sorted(IDIOMS.keys(), key=len, reverse=True)
_MAX_IDIOM_SPAN = 4  # max tokens to glue when probing for an idiom


def _match_idioms(raw: list, clause: dict):
    used = [False] * len(raw)
    out = []
    i, n = 0, len(raw)
    while i < n:
        matched = False
        for span in range(min(_MAX_IDIOM_SPAN, n - i), 0, -1):
            glued = "".join(raw[i:i + span])
            if glued in IDIOMS:
                out.append(Phrase(surface=glued, pattern="idiom", clause=clause))
                for k in range(i, i + span):
                    used[k] = True
                i += span
                matched = True
                break
        if not matched:
            i += 1
    return out, used
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_extract_idiom -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add core/phrases/extract.py tests/test_extract_idiom.py
git commit -m "feat: idiom strategy for phrase extraction"
```

---

## Task 7: Extraction — POS grammar strategy

Adds slot predicates and the noun-led / verb-led / standalone-descriptor grammar.

**Files:**
- Modify: `core/phrases/extract.py`
- Test: `tests/test_extract_grammar.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_extract_grammar.py
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.phrases import extract


def tags(pairs):
    """Helper: build (raw, tags) from a list of (token, tag)."""
    return [t for t, _ in pairs], [(t, g) for t, g in pairs]


class TestGrammar(unittest.TestCase):
    def test_p1_noun_plus_descriptor(self):
        raw, tg = tags([("อาหาร", "NOUN"), ("อร่อย", "VERB"), ("มากๆ", "ADV")])
        out, used = extract._match_grammar(raw, tg, [False] * 3, {})
        p = out[0]
        self.assertEqual(p.head_noun, "อาหาร")
        self.assertIn("อร่อย", p.descriptor_tokens)
        self.assertNotIn("มากๆ", p.descriptor_tokens)   # intensifier excluded
        self.assertEqual(p.pattern, "P1")

    def test_p2_negation(self):
        raw, tg = tags([("ราคา", "NOUN"), ("ไม่", "NEG"), ("แพง", "VERB")])
        out, _ = extract._match_grammar(raw, tg, [False] * 3, {})
        p = out[0]
        self.assertEqual(p.head_noun, "ราคา")
        self.assertEqual(p.descriptor_tokens, ["ไม่", "แพง"])
        self.assertEqual(p.pattern, "P2")

    def test_p3_verb_plus_descriptor(self):
        raw, tg = tags([("รอ", "VERB"), ("นาน", "VERB")])
        out, _ = extract._match_grammar(raw, tg, [False] * 2, {})
        self.assertIsNone(out[0].head_noun)
        self.assertEqual(out[0].descriptor_tokens, ["รอ", "นาน"])
        self.assertEqual(out[0].pattern, "P3")

    def test_standalone_descriptor_compound(self):
        raw, tg = tags([("เย็น", "VERB"), ("สบาย", "VERB")])
        out, _ = extract._match_grammar(raw, tg, [False] * 2, {})
        self.assertIsNone(out[0].head_noun)
        self.assertEqual(out[0].descriptor_tokens, ["เย็น", "สบาย"])
        self.assertEqual(out[0].pattern, "P7")

    def test_bare_noun_not_emitted(self):
        raw, tg = tags([("อาหาร", "NOUN")])
        out, _ = extract._match_grammar(raw, tg, [False], {})
        self.assertEqual(out, [])

    def test_respects_used_flags(self):
        raw, tg = tags([("อาหาร", "NOUN"), ("อร่อย", "VERB")])
        out, _ = extract._match_grammar(raw, tg, [True, True], {})
        self.assertEqual(out, [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_extract_grammar -v`
Expected: FAIL — `AttributeError: module ... has no attribute '_match_grammar'`

- [ ] **Step 3: Write minimal implementation**

Append to `core/phrases/extract.py`:

```python
def _is_noun(tok: str, tag: str) -> bool:
    return tag in postag.NOUN_TAGS or tok in NOUN_TO_ASPECT


def _is_desc(tok: str, tag: str) -> bool:
    return (tag in postag.STATIVE_TAGS
            or negation.word_polarity(tok) != 0
            or tok in DESCRIPTOR_ASPECT_HINTS)


def _is_neg(tok: str) -> bool:
    return tok in negation.NEGATORS or tok.startswith("ไม่")


def _is_filler(tok: str) -> bool:
    return tok in FILLERS


def _collect_descriptor_run(raw, tags, j, n):
    """From index j, collect descriptor tokens (skipping fillers, excluding
    intensifiers). Returns (descriptor_tokens, end_index, span_tokens)."""
    desc, span = [], []
    while j < n:
        tok, tag = raw[j], tags[j][1]
        if tok in INTENSIFIERS:
            span.append(tok); j += 1; continue          # part of span, not descriptor
        if _is_filler(tok):
            span.append(tok); j += 1; continue          # dropped filler
        if _is_desc(tok, tag):
            desc.append(tok); span.append(tok); j += 1; continue
        break
    return desc, j, span


def _match_grammar(raw, tags, used, clause):
    out = []
    i, n = 0, len(raw)
    while i < n:
        if used[i]:
            i += 1; continue
        tok, tag = raw[i], tags[i][1]

        # noun-led: NOUN (NEG)? descriptor-run   -> P1 / P2
        if _is_noun(tok, tag):
            j = i + 1
            neg = []
            if j < n and _is_neg(raw[j]) and j + 1 < n and _is_desc(raw[j + 1], tags[j + 1][1]):
                neg = [raw[j]]; j += 1
            desc, j2, span = _collect_descriptor_run(raw, tags, j, n)
            if desc:
                dtoks = neg + desc
                out.append(Phrase(
                    surface=" ".join(raw[i:j2]), head_noun=tok,
                    descriptor_tokens=dtoks, pattern="P2" if neg else "P1",
                    clause=clause))
                for k in range(i, j2):
                    used[k] = True
                i = j2; continue

        # verb-led: VERB descriptor-run  -> P3  (รอ นาน)
        if tag in postag.VERB_TAGS and not _is_noun(tok, tag):
            desc, j2, span = _collect_descriptor_run(raw, tags, i + 1, n)
            if desc:
                out.append(Phrase(
                    surface=" ".join(raw[i:j2]), head_noun=None,
                    descriptor_tokens=[tok] + desc, pattern="P3", clause=clause))
                for k in range(i, j2):
                    used[k] = True
                i = j2; continue

        # standalone descriptor / compound -> P7 (handled later by quality/canonical)
        if _is_desc(tok, tag):
            desc, j2, span = _collect_descriptor_run(raw, tags, i, n)
            if desc:
                out.append(Phrase(
                    surface=" ".join(raw[i:j2]), head_noun=None,
                    descriptor_tokens=desc, pattern="P7", clause=clause))
                for k in range(i, j2):
                    used[k] = True
                i = j2; continue

        i += 1
    return out, used
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_extract_grammar -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add core/phrases/extract.py tests/test_extract_grammar.py
git commit -m "feat: POS chunk grammar (P1/P2/P3/P7) for phrase extraction"
```

---

## Task 8: Extraction — fallback + public `extract()`

Adds the lexicon-adjacency fallback (POS off/UNK) and the top-level orchestrator.

**Files:**
- Modify: `core/phrases/extract.py`
- Test: `tests/test_extract_public.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_extract_public.py
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.phrases import extract


class TestPublicExtract(unittest.TestCase):
    def _clause(self, raw):
        return {"raw_tokens": raw, "tokens": raw, "tokens_base": raw, "clean": "".join(raw)}

    def test_extract_runs_with_real_tagger(self):
        # End-to-end through the real PyThaiNLP path; must not crash and must
        # produce at least one bound phrase for a clear input.
        c = self._clause(["อาหาร", "อร่อย"])
        out = extract.extract(c)
        self.assertTrue(any(p.head_noun == "อาหาร" for p in out))

    def test_fallback_when_tags_unknown(self):
        # Force UNK tags -> grammar finds nothing -> fallback adjacency must fire
        raw = ["บริการ", "ช้า"]
        out = extract._match_fallback(raw, [False, False],
                                      self._clause(raw))
        self.assertTrue(any(p.head_noun == "บริการ" and "ช้า" in p.descriptor_tokens
                            for p in out))

    def test_idiom_takes_priority_over_grammar(self):
        c = self._clause(["ติด", "ริมน้ำ"])
        out = extract.extract(c)
        self.assertTrue(any(p.pattern == "idiom" and p.surface == "ติดริมน้ำ"
                            for p in out))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_extract_public -v`
Expected: FAIL — `AttributeError: ... '_match_fallback'` / `'extract'`

- [ ] **Step 3: Write minimal implementation**

Append to `core/phrases/extract.py`:

```python
def _match_fallback(raw, used, clause):
    """Lexicon adjacency (Architecture-1 behavior): known noun + known descriptor,
    used when POS is unavailable/UNK or the grammar found nothing in a span."""
    out = []
    n = len(raw)
    for i in range(n - 1):
        if used[i] or used[i + 1]:
            continue
        a, b = raw[i], raw[i + 1]
        if a in NOUN_TO_ASPECT and negation.word_polarity(b) != 0:
            out.append(Phrase(surface=f"{a} {b}", head_noun=a,
                              descriptor_tokens=[b], pattern="fallback", clause=clause))
            used[i] = used[i + 1] = True
    return out


def extract(clause: dict) -> list:
    """Public Stage-1 entry point. clause must have 'raw_tokens'."""
    raw = clause.get("raw_tokens") or []
    if not raw:
        return []
    phrases, used = _match_idioms(raw, clause)
    tags = postag.pos_tag(raw)
    if postag.available():
        g, used = _match_grammar(raw, tags, used, clause)
        phrases += g
    phrases += _match_fallback(raw, used, clause)
    return phrases
```

> Note: `_match_idioms` currently returns its own `used` list; the grammar must
> respect it. Update `_match_idioms`'s return to share the flags — it already returns
> `(out, used)`, and `extract` passes that `used` into `_match_grammar`. Confirm the
> idiom `used` flags propagate (they do, since `extract` reuses the returned list).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_extract_public -v`
Expected: PASS (3 tests). If `test_extract_runs_with_real_tagger` fails because the
installed PyThaiNLP tags `อร่อย` outside `STATIVE_TAGS`, add the observed tag to
`postag.STATIVE_TAGS` and re-run (this is the confirmation step from Task 2).

- [ ] **Step 5: Run all extract tests**

Run: `python -m unittest tests.test_extract_idiom tests.test_extract_grammar tests.test_extract_public -v`
Expected: PASS (all)

- [ ] **Step 6: Commit**

```bash
git add core/phrases/extract.py tests/test_extract_public.py
git commit -m "feat: fallback adjacency + public extract() orchestrator"
```

---

## Task 9: Quality filtering (`core/phrases/quality.py`)

**Files:**
- Create: `core/phrases/quality.py`
- Test: `tests/test_quality.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_quality.py
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.phrases.model import Phrase
from core.phrases import quality


class TestQuality(unittest.TestCase):
    def test_keeps_bound_phrase(self):
        p = Phrase(surface="อาหาร อร่อย", head_noun="อาหาร",
                   descriptor_tokens=["อร่อย"], pattern="P1")
        self.assertEqual(len(quality.filter_phrases([p], ["food"])), 1)

    def test_rejects_meta_verb(self):
        p = Phrase(surface="แนะนำ", descriptor_tokens=["แนะนำ"], pattern="P7")
        self.assertEqual(quality.filter_phrases([p], ["food"]), [])

    def test_rejects_bare_noun(self):
        p = Phrase(surface="อาหาร", head_noun="อาหาร", descriptor_tokens=[], pattern="P1")
        self.assertEqual(quality.filter_phrases([p], ["food"]), [])

    def test_keeps_descriptor_compound(self):
        p = Phrase(surface="เย็น สบาย", descriptor_tokens=["เย็น", "สบาย"], pattern="P7")
        out = quality.filter_phrases([p], ["food", "atmosphere"])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].aspect, "atmosphere")  # via hint

    def test_keeps_hinted_single_descriptor(self):
        p = Phrase(surface="คึกคัก", descriptor_tokens=["คึกคัก"], pattern="P7")
        out = quality.filter_phrases([p], ["food", "atmosphere"])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].aspect, "atmosphere")

    def test_bare_descriptor_high_conf_single_clause_aspect(self):
        # "ดี" not in hints; clause has exactly one aspect -> provisional high conf
        p = Phrase(surface="ดี", descriptor_tokens=["ดี"], pattern="P7")
        out = quality.filter_phrases([p], ["atmosphere"])
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0].aspect, out[0].aspect_conf), ("atmosphere", "high"))

    def test_bare_descriptor_low_conf_dropped(self):
        # "ดี" not in hints; clause ambiguous (>=2 aspects) -> dropped (no hallucination)
        p = Phrase(surface="ดี", descriptor_tokens=["ดี"], pattern="P7")
        self.assertEqual(quality.filter_phrases([p], ["food", "atmosphere"]), [])

    def test_idiom_always_kept(self):
        p = Phrase(surface="ติดริมน้ำ", pattern="idiom")
        self.assertEqual(len(quality.filter_phrases([p], [])), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_quality -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.phrases.quality'`

- [ ] **Step 3: Write minimal implementation**

```python
# core/phrases/quality.py
"""Stage 2 — quality filtering. Decides worthiness; sets provisional aspect +
confidence for bare-descriptor (P7) phrases so stage 3 can gate synthesis."""
from core.lexicon import META_VERBS, DESCRIPTOR_ASPECT_HINTS

MIN_LEN = 2


def _provisional_aspect(p, clause_aspects):
    """Return (aspect, conf) for a standalone descriptor phrase, or (None, 'low')."""
    for tok in p.descriptor_tokens:
        if tok in DESCRIPTOR_ASPECT_HINTS:
            return DESCRIPTOR_ASPECT_HINTS[tok], "high"
    joined = "".join(p.descriptor_tokens)
    if joined in DESCRIPTOR_ASPECT_HINTS:
        return DESCRIPTOR_ASPECT_HINTS[joined], "high"
    if len(clause_aspects) == 1:
        return clause_aspects[0], "high"
    return None, "low"


def filter_phrases(phrases: list, clause_aspects: list) -> list:
    out = []
    for p in phrases:
        if p.pattern == "idiom":
            out.append(p); continue

        # reject meta/recommendation verbs
        if any(t in META_VERBS for t in p.descriptor_tokens):
            continue

        # bound phrase (noun + descriptor) -> keep
        if p.head_noun and p.descriptor_tokens:
            out.append(p); continue

        # bare noun, no descriptor -> reject
        if p.head_noun and not p.descriptor_tokens:
            continue

        # standalone descriptor (P7 / P3)
        if p.descriptor_tokens:
            joined = "".join(p.descriptor_tokens)
            if len(joined) < MIN_LEN:
                continue
            # compound (>=2) or hinted single -> keep as-is, route via hint/clause
            asp, conf = _provisional_aspect(p, clause_aspects)
            is_compound = len(p.descriptor_tokens) >= 2
            is_hinted = any(t in DESCRIPTOR_ASPECT_HINTS for t in p.descriptor_tokens)
            if is_compound or is_hinted:
                p.aspect, p.aspect_conf = asp, (conf if asp else "low")
                out.append(p); continue
            # bare single descriptor -> needs synthesis; keep only at high confidence
            if conf == "high" and asp:
                p.aspect, p.aspect_conf = asp, "high"
                out.append(p); continue
            # otherwise drop (no hallucinated insight)
            continue
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_quality -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add core/phrases/quality.py tests/test_quality.py
git commit -m "feat: phrase quality filtering with gated P7 confidence"
```

---

## Task 10: Canonicalization (`core/phrases/canonical.py`)

**Files:**
- Create: `core/phrases/canonical.py`
- Test: `tests/test_canonical.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_canonical.py
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.phrases.model import Phrase
from core.phrases import canonical


class TestCanonical(unittest.TestCase):
    def test_bound_phrase(self):
        p = Phrase(surface="อาหาร อร่อย มากๆ", head_noun="อาหาร",
                   descriptor_tokens=["อร่อย"], pattern="P1")
        self.assertEqual(canonical.canonicalize(p).canonical, "อาหารอร่อย")

    def test_negation_kept(self):
        p = Phrase(surface="ราคา ไม่ แพง", head_noun="ราคา",
                   descriptor_tokens=["ไม่", "แพง"], pattern="P2")
        self.assertEqual(canonical.canonicalize(p).canonical, "ราคาไม่แพง")

    def test_compound_descriptor_no_synthesis(self):
        p = Phrase(surface="เย็น สบาย", descriptor_tokens=["เย็น", "สบาย"],
                   pattern="P7", aspect="atmosphere", aspect_conf="high")
        self.assertEqual(canonical.canonicalize(p).canonical, "เย็นสบาย")

    def test_bare_descriptor_synthesizes_head_noun(self):
        p = Phrase(surface="อร่อย", descriptor_tokens=["อร่อย"], pattern="P7",
                   aspect="food", aspect_conf="high")
        self.assertEqual(canonical.canonicalize(p).canonical, "อาหารอร่อย")

    def test_hinted_single_descriptor_not_synthesized(self):
        # คึกคัก is hinted (specific) -> kept as-is, not turned into บรรยากาศคึกคัก
        p = Phrase(surface="คึกคัก", descriptor_tokens=["คึกคัก"], pattern="P7",
                   aspect="atmosphere", aspect_conf="high")
        self.assertEqual(canonical.canonicalize(p).canonical, "คึกคัก")

    def test_idiom_uses_canonical_map(self):
        p = Phrase(surface="ริมน้ำ", pattern="idiom")
        self.assertEqual(canonical.canonicalize(p).canonical, "ติดริมน้ำ")

    def test_defensive_intensifier_strip(self):
        p = Phrase(surface="อาหาร อร่อย", head_noun="อาหาร",
                   descriptor_tokens=["อร่อย", "มาก"], pattern="P1")
        self.assertEqual(canonical.canonicalize(p).canonical, "อาหารอร่อย")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_canonical -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.phrases.canonical'`

- [ ] **Step 3: Write minimal implementation**

```python
# core/phrases/canonical.py
"""Stage 3 — build the canonical phrase string; gated head-noun synthesis."""
from core.lexicon import IDIOMS, INTENSIFIERS, FILLERS, ASPECT_HEAD_NOUN, DESCRIPTOR_ASPECT_HINTS


def _clean_descriptor(tokens: list) -> str:
    return "".join(t for t in tokens if t not in INTENSIFIERS and t not in FILLERS)


def canonicalize(p):
    if p.pattern == "idiom":
        p.canonical = IDIOMS[p.surface]["canonical"]
        return p

    desc = _clean_descriptor(p.descriptor_tokens)

    if p.head_noun:                                   # bound phrase
        p.canonical = p.head_noun + desc
        return p

    # standalone descriptor
    is_compound = len(p.descriptor_tokens) >= 2
    is_hinted = any(t in DESCRIPTOR_ASPECT_HINTS for t in p.descriptor_tokens)
    if is_compound or is_hinted:
        p.canonical = desc                            # specific enough; keep as-is
        return p

    # bare single descriptor -> synthesize head noun (only reaches here at high conf)
    if p.aspect_conf == "high" and p.aspect in ASPECT_HEAD_NOUN:
        p.canonical = ASPECT_HEAD_NOUN[p.aspect] + desc
    else:
        p.canonical = desc                            # safety net; quality usually drops these
    return p
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_canonical -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add core/phrases/canonical.py tests/test_canonical.py
git commit -m "feat: phrase canonicalization with gated head-noun synthesis"
```

---

## Task 11: Synonym aggregation (`core/phrases/synonyms.py`)

**Files:**
- Create: `core/phrases/synonyms.py`
- Test: `tests/test_synonyms.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_synonyms.py
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.phrases.model import Phrase
from core.phrases import synonyms


def _p(canonical):
    return Phrase(surface=canonical, canonical=canonical)


class TestSynonyms(unittest.TestCase):
    def test_price_variants_merge(self):
        a = synonyms.aggregate(_p("ราคาไม่แพง"))
        b = synonyms.aggregate(_p("คุ้มค่า"))
        self.assertEqual(a.concept, b.concept)
        self.assertEqual(a.label, "ราคาคุ้มค่า")

    def test_antonyms_do_not_merge(self):
        good = synonyms.aggregate(_p("ราคาไม่แพง"))
        bad = synonyms.aggregate(_p("ราคาแพง"))
        self.assertNotEqual(good.concept, bad.concept)

    def test_distinct_descriptors_stay_separate(self):
        a = synonyms.aggregate(_p("อร่อย"))
        b = synonyms.aggregate(_p("จัดจ้าน"))
        self.assertNotEqual(a.concept, b.concept)
        self.assertEqual(a.concept, "อร่อย")   # identity when ungrouped
        self.assertEqual(a.label, "อร่อย")

    def test_ungrouped_identity(self):
        p = synonyms.aggregate(_p("ปลาสด"))
        self.assertEqual((p.concept, p.label), ("ปลาสด", "ปลาสด"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_synonyms -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.phrases.synonyms'`

- [ ] **Step 3: Write minimal implementation**

```python
# core/phrases/synonyms.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_synonyms -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add core/phrases/synonyms.py tests/test_synonyms.py
git commit -m "feat: conservative synonym aggregation layer"
```

---

## Task 12: Aspect resolver + clause detection (`core/aspect.py`)

Adds `detect_clause_aspects()` and the 4-tier `route_aspect()`. Existing
`tag_aspects`/`aspect_sentiment_summary` are left intact (still used for the donut
summary).

**Files:**
- Modify: `core/aspect.py`
- Test: `tests/test_aspect_route.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_aspect_route.py
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.phrases.model import Phrase
from core import aspect


class TestRouteAspect(unittest.TestCase):
    def test_tier1_idiom(self):
        p = Phrase(surface="ติดริมน้ำ", pattern="idiom")
        self.assertEqual(aspect.route_aspect(p, [])[0], "atmosphere")

    def test_tier1_synonym_concept(self):
        p = Phrase(surface="คุ้มค่า", canonical="คุ้มค่า", concept="price_good")
        self.assertEqual(aspect.route_aspect(p, [])[0], "food")

    def test_tier2_head_noun(self):
        p = Phrase(surface="ราคา ไม่ แพง", head_noun="ราคา",
                   descriptor_tokens=["ไม่", "แพง"], concept="x")
        self.assertEqual(aspect.route_aspect(p, ["service"])[0], "food")

    def test_tier3_single_clause_aspect(self):
        p = Phrase(surface="หยาบคาย", descriptor_tokens=["หยาบคาย"], concept="x")
        self.assertEqual(aspect.route_aspect(p, ["service"])[0], "service")

    def test_tier4_descriptor_hint(self):
        p = Phrase(surface="คึกคัก", descriptor_tokens=["คึกคัก"], concept="x")
        self.assertEqual(aspect.route_aspect(p, ["food", "service"])[0], "atmosphere")

    def test_uncategorized(self):
        p = Phrase(surface="งง", descriptor_tokens=["งง"], concept="x")
        self.assertEqual(aspect.route_aspect(p, ["food", "service"])[0], None)

    def test_detect_clause_aspects(self):
        clause = {"raw_tokens": ["พนักงาน", "ใจดี"], "tokens_base": ["พนักงาน", "ใจดี"]}
        self.assertIn("service", aspect.detect_clause_aspects(clause))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_aspect_route -v`
Expected: FAIL — `AttributeError: module 'core.aspect' has no attribute 'route_aspect'`

- [ ] **Step 3: Write minimal implementation**

Append to `core/aspect.py`:

```python
from core import lexicon  # noqa: E402  (added for phrase-level routing)


def detect_clause_aspects(clause: dict) -> list:
    """Aspects a clause talks about, from head nouns + descriptor hints over its
    raw tokens. Order-stable, de-duplicated."""
    toks = clause.get("raw_tokens") or clause.get("tokens_base") or []
    found = []
    for t in toks:
        a = lexicon.NOUN_TO_ASPECT.get(t) or lexicon.DESCRIPTOR_ASPECT_HINTS.get(t)
        if a and a not in found:
            found.append(a)
    return found


def route_aspect(phrase, clause_aspects: list):
    """4-tier resolver: idiom/concept -> head noun -> single clause aspect -> hint.
    Returns (aspect|None, conf)."""
    # tier 1 — curated mappings (idiom or synonym concept)
    if phrase.pattern == "idiom" and phrase.surface in lexicon.IDIOMS:
        return lexicon.IDIOMS[phrase.surface]["aspect"], "high"
    if phrase.concept in lexicon.SYNONYM_GROUPS:
        return lexicon.SYNONYM_GROUPS[phrase.concept]["aspect"], "high"
    # tier 2 — head noun
    if phrase.head_noun and phrase.head_noun in lexicon.NOUN_TO_ASPECT:
        return lexicon.NOUN_TO_ASPECT[phrase.head_noun], "high"
    # tier 3 — unambiguous clause context only
    if len(clause_aspects) == 1:
        return clause_aspects[0], "high"
    # tier 4 — descriptor hint
    for t in phrase.descriptor_tokens:
        if t in lexicon.DESCRIPTOR_ASPECT_HINTS:
            return lexicon.DESCRIPTOR_ASPECT_HINTS[t], "medium"
    joined = "".join(phrase.descriptor_tokens)
    if joined in lexicon.DESCRIPTOR_ASPECT_HINTS:
        return lexicon.DESCRIPTOR_ASPECT_HINTS[joined], "medium"
    return None, "low"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_aspect_route -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add core/aspect.py tests/test_aspect_route.py
git commit -m "feat: 4-tier aspect resolver and clause-aspect detection"
```

---

## Task 13: Phrase sentiment in context (`core/sentiment.py`)

Adds `classify_phrase()` — independent of extraction, classifies in the source
clause context, with the lexicon backstop when the model is off.

**Files:**
- Modify: `core/sentiment.py`
- Test: `tests/test_phrase_sentiment.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_phrase_sentiment.py
import os, sys, unittest
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from core.phrases.model import Phrase
from core import sentiment


class TestPhraseSentiment(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(config, "get_use_model", return_value=False)
        p.start(); self.addCleanup(p.stop)

    def test_positive_descriptor_backstop(self):
        ph = Phrase(surface="อาหาร อร่อย", descriptor_tokens=["อร่อย"],
                    clause={"clean": "อาหารอร่อย", "tokens": ["อาหาร", "อร่อย"]})
        self.assertEqual(sentiment.classify_phrase(ph), "positive")

    def test_negative_descriptor_backstop(self):
        ph = Phrase(surface="รอ นาน", descriptor_tokens=["รอนาน"],
                    clause={"clean": "รอนาน", "tokens": ["รอนาน"]})
        self.assertEqual(sentiment.classify_phrase(ph), "negative")

    def test_ambiguous_phrase_uses_clause_context_not_phrase(self):
        # คนเยอะ has no fixed polarity; sentiment must come from the clause backstop
        ph = Phrase(surface="คน เยอะ", descriptor_tokens=["เยอะ"],
                    clause={"clean": "คนเยอะแต่บริการแย่", "tokens": ["คนเยอะ", "บริการแย่"]})
        self.assertEqual(sentiment.classify_phrase(ph), "negative")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_phrase_sentiment -v`
Expected: FAIL — `AttributeError: module 'core.sentiment' has no attribute 'classify_phrase'`

- [ ] **Step 3: Write minimal implementation**

Append to `core/sentiment.py`:

```python
def classify_phrase(phrase) -> str:
    """Stage 6 — sentiment for one phrase occurrence, decided IN CONTEXT
    (its source clause), independent of extraction.

    Model on : WangchanBERTa on the source clause text.
    Model off: negation-aware lexicon over the clause tokens (backstop); falls back
               to the phrase's own descriptor polarity, else neutral.
    """
    clause = phrase.clause or {}
    if config.get_use_model():
        try:
            return _predict_model(clause.get("clean", phrase.surface))
        except Exception as e:
            global _model_status
            if _model_status != "failed":
                _model_status = "failed"
                print(f"[sentiment] WangchanBERTa unavailable, using lexicon: {e}")
    # backstop: clause context first, then the phrase descriptor
    tokens = clause.get("tokens") or phrase.descriptor_tokens
    label = _predict_lexicon(tokens)
    if label == "neutral" and phrase.descriptor_tokens:
        return _predict_lexicon(phrase.descriptor_tokens)
    return label
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_phrase_sentiment -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add core/sentiment.py tests/test_phrase_sentiment.py
git commit -m "feat: context-based per-phrase sentiment classification"
```

---

## Task 14: Dashboard aggregation (`core/phrases/aggregate.py`)

Counts phrases by (aspect, sentiment, concept) and emits the existing dashboard
contract so templates/DB/export are unchanged.

**Files:**
- Create: `core/phrases/aggregate.py`
- Test: `tests/test_aggregate.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_aggregate.py
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.phrases.model import Phrase
from core.phrases import aggregate


def _ph(concept, label, aspect, sentiment):
    return Phrase(surface=label, canonical=label, concept=concept, label=label,
                  aspect=aspect, sentiment=sentiment)


class TestAggregate(unittest.TestCase):
    def test_shape_and_counts(self):
        # aggregate uses the dashboard contract keys (food/service/ambience);
        # the pipeline maps phrase "atmosphere" -> "ambience" before this stage.
        phrases = [
            _ph("อาหารอร่อย", "อาหารอร่อย", "food", "positive"),
            _ph("อาหารอร่อย", "อาหารอร่อย", "food", "positive"),
            _ph("price_good", "ราคาคุ้มค่า", "food", "positive"),
            _ph("รอนาน", "รอนาน", "service", "negative"),
        ]
        out = aggregate.build(phrases)
        self.assertEqual(set(out), {"food", "service", "ambience"})
        self.assertEqual(set(out["food"]), {"positive", "neutral", "negative"})
        food_pos = {d["word"]: d["count"] for d in out["food"]["positive"]}
        self.assertEqual(food_pos["อาหารอร่อย"], 2)
        self.assertEqual(food_pos["ราคาคุ้มค่า"], 1)

    def test_same_concept_splits_across_sentiment(self):
        phrases = [
            _ph("คนเยอะ", "คนเยอะ", "ambience", "positive"),
            _ph("คนเยอะ", "คนเยอะ", "ambience", "negative"),
        ]
        out = aggregate.build(phrases)
        self.assertEqual(out["ambience"]["positive"][0]["count"], 1)
        self.assertEqual(out["ambience"]["negative"][0]["count"], 1)

    def test_drops_uncategorized_and_unsented(self):
        phrases = [_ph("x", "x", None, "positive"), _ph("y", "y", "food", None)]
        out = aggregate.build(phrases)
        self.assertEqual(out["food"]["positive"], [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_aggregate -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.phrases.aggregate'`

- [ ] **Step 3: Write minimal implementation**

```python
# core/phrases/aggregate.py
"""Stage 7 — count phrases by (aspect, sentiment, concept) into the dashboard
contract: {aspect: {positive:[{word,count}], neutral:[...], negative:[...]}}."""
from core.lexicon import ASPECT_LEXICON

_SENTS = ("positive", "neutral", "negative")
_ASPECTS = tuple(ASPECT_LEXICON.keys())   # food, service, atmosphere
TOP_N = 6


def build(phrases: list) -> dict:
    # buckets[aspect][sentiment][concept] = [count, label]
    buckets = {a: {s: {} for s in _SENTS} for a in _ASPECTS}
    for p in phrases:
        if p.aspect not in buckets or p.sentiment not in _SENTS:
            continue
        slot = buckets[p.aspect][p.sentiment]
        if p.concept in slot:
            slot[p.concept][0] += 1
        else:
            slot[p.concept] = [1, p.label or p.canonical]

    result = {}
    for a in _ASPECTS:
        result[a] = {}
        for s in _SENTS:
            items = [(label, cnt) for cnt, label in
                     ([v[0], v[1]] for v in buckets[a][s].values())]
            # sort by count desc, then label length desc, then text
            items.sort(key=lambda x: (x[1], len(x[0]), x[0]), reverse=True)
            result[a][s] = [{"word": label, "count": cnt}
                            for label, cnt in items[:TOP_N]]
    return result
```

> Note on the comprehension: `buckets[a][s]` maps concept → `[count, label]`. The
> generator rebuilds `(label, count)` tuples for sorting. Keep it simple — if it reads
> awkwardly during implementation, replace with an explicit loop that appends
> `(label, count)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_aggregate -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add core/phrases/aggregate.py tests/test_aggregate.py
git commit -m "feat: dashboard aggregation preserving the keywords contract"
```

---

## Task 15: Wire the pipeline (`core/pipeline.py`)

Replaces the keyword stage with the new phrase pipeline; keeps output keys.

**Files:**
- Modify: `core/pipeline.py`
- Test: `tests/test_integration.py` (extend existing)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_integration.py` inside `TestPipelineSmoke`:

```python
    def test_keywords_are_phrases_not_bare_nouns(self):
        bad = {"อาหาร", "เมนู", "ร้าน", "ดี", "อร่อย", "ชอบ", "แนะนำ"}
        words = []
        for asp in self.result["keywords"].values():
            for bucket in asp.values():
                words += [k["word"] for k in bucket]
        self.assertTrue(words, "expected some phrases")
        # no bare single-word noise terms in output
        self.assertEqual([w for w in words if w in bad], [])

    def test_keywords_contract_shape(self):
        kw = self.result["keywords"]
        self.assertEqual(set(kw), {"food", "service", "ambience"})
        for asp in kw.values():
            self.assertEqual(set(asp), {"positive", "neutral", "negative"})
```

> Note: the dashboard aspect keys are `food`/`service`/`ambience` (the existing
> `ASPECT_LEXICON` keys). `aggregate.build` already uses those keys. The new phrase
> `aspect` values (`food`/`service`/`atmosphere`) must be mapped to the contract keys:
> `atmosphere` → `ambience`. Handle this mapping in `pipeline` (Step 3).

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_integration -v`
Expected: FAIL — bare nouns still present (old keyword path) / shape mismatch.

- [ ] **Step 3: Write minimal implementation**

Rewrite `core/pipeline.py` `run_analysis` keyword section. Replace the keyword/topics
block and add the phrase stages:

```python
from core import scraper, preprocess, sentiment, aspect, keywords, insights
from core.phrases import extract, quality, canonical, synonyms, aggregate

# phrase aspect value -> dashboard contract key
_ASPECT_KEY = {"food": "food", "service": "service", "atmosphere": "ambience"}


def _phrase_pipeline(reviews: list) -> dict:
    collected = []
    for r in reviews:
        for clause in r.get("clauses", []):
            clause_aspects = aspect.detect_clause_aspects(clause)
            raw = extract.extract(clause)                       # stage 1
            kept = quality.filter_phrases(raw, clause_aspects)  # stage 2
            for p in kept:
                canonical.canonicalize(p)                       # stage 3
                synonyms.aggregate(p)                           # stage 4
                if p.aspect is None:                            # stage 5 (skip if set)
                    a, conf = aspect.route_aspect(p, clause_aspects)
                    p.aspect, p.aspect_conf = a, conf
                if p.aspect is None:
                    continue
                p.aspect = _ASPECT_KEY.get(p.aspect, p.aspect)  # map to contract key
                p.sentiment = sentiment.classify_phrase(p)      # stage 6
                collected.append(p)
    return aggregate.build(collected)                           # stage 7
```

Then in `run_analysis`, replace:

```python
    kw = keywords.extract_keywords(reviews)
```

with:

```python
    kw = _phrase_pipeline(reviews)
```

Keep `topics = keywords.extract_topics(reviews)` and everything else unchanged.

> `aggregate.build` keys are `food`/`service`/`atmosphere` from `ASPECT_LEXICON`.
> Confirm: `ASPECT_LEXICON` keys are `food`/`service`/`ambience`. Therefore set
> `_ASPECTS` in `aggregate.py` correctly — it already derives from `ASPECT_LEXICON`,
> so the buckets use `ambience`. The `_ASPECT_KEY` map above converts phrase
> `atmosphere` → `ambience` before aggregation, so they align. (Double-check this key
> name during execution; it is the one cross-module coupling.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_integration -v`
Expected: PASS (existing + 2 new). The existing
`test_negation_keyword_flows_to_output` should still pass (e.g., `ราคาไม่แพง`,
`ไม่อร่อย`-style phrases appear).

- [ ] **Step 5: Run the full suite**

Run: `python -m unittest discover -s tests -v`
Expected: PASS (all). Fix any aspect-key mismatch surfaced here.

- [ ] **Step 6: Manual smoke check on the worked example**

Run:
```bash
python -X utf8 -c "import json; from core import pipeline; from unittest import mock; import config; \
mp=mock.patch.object(config,'get_apify_token',return_value=''); mp.start(); \
mp2=mock.patch.object(config,'get_use_model',return_value=False); mp2.start(); \
r=pipeline.run_analysis(''); print(json.dumps(r['keywords'], ensure_ascii=False, indent=1))" > _smoke.json 2>&1
```
Then open `_smoke.json` and confirm phrases (not bare nouns) appear under
food/service/ambience. Delete it: `rm -f _smoke.json`.

- [ ] **Step 7: Commit**

```bash
git add core/pipeline.py tests/test_integration.py
git commit -m "feat: wire phrase-extraction pipeline into run_analysis"
```

---

## Task 16: Remove superseded code + update README

**Files:**
- Delete: `core/keyphrase.py` (and its tests if they only cover the old path)
- Modify: `core/keywords.py` (drop `extract_keywords` + helpers; keep `extract_topics`)
- Delete: `tests/test_keyphrase.py`, `tests/test_keywords_attribution.py` (old-path tests)
- Modify: `README.md`

- [ ] **Step 1: Confirm nothing imports the removed code**

Run: `python -m unittest discover -s tests -v`
Then search for stale imports:
Run (PowerShell): `Select-String -Path core\*.py,core\phrases\*.py -Pattern "keyphrase|extract_keywords"`
Expected: only `keywords.py` (definition) and no remaining callers of `extract_keywords` besides what you are about to remove.

- [ ] **Step 2: Remove `extract_keywords` from `core/keywords.py`**

Delete `extract_keywords` and its private helpers (`_iter_clauses` may be shared with
`extract_topics` — if so, keep it). Keep `extract_topics` and the module docstring
(trim the parts describing the removed function).

- [ ] **Step 3: Delete superseded modules and tests**

```bash
git rm core/keyphrase.py tests/test_keyphrase.py tests/test_keywords_attribution.py
```

- [ ] **Step 4: Run the full suite**

Run: `python -m unittest discover -s tests -v`
Expected: PASS (no import errors; `extract_topics` tests still pass).

- [ ] **Step 5: Update README**

In `README.md`, make these concrete edits:
1. **Remove the TF-IDF claim** (currently in the code-map line for `keywords.py` and
   in the "ทำเสร็จแล้ว" checklist). Replace with: *"สกัดวลีความเห็น (opinion
   phrases) ด้วย POS-pattern chunking + พจนานุกรมโดเมน"*.
2. **Add the new modules** to the code-map: `core/postag.py`, `core/clause.py`,
   `core/negation.py`, `core/phrases/` (extract/quality/canonical/synonyms/aggregate).
3. **Update the pipeline diagram** to:
   `URL → scraper → preprocess (clause split) → extract → quality → canonical →
   synonyms → aspect → sentiment → aggregate → insights`.
4. **Add a "วิธีการ (Methodology)" section** summarizing: clause-level aspect
   sentiment, negation handling, POS-chunking phrase extraction, conservative synonym
   aggregation, 4-tier aspect routing.
5. **Add a "ข้อจำกัด (Limitations)" section**: contrastive split only on แต่-family;
   lexicon-bounded polarity in fallback; one-token negation scope; phrase/aspect
   quality validated qualitatively (not on a labeled gold set).
6. **Add the test command**: `python -m unittest discover -s tests` and note pytest
   is not a dependency.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: remove superseded keyword path; document phrase pipeline in README"
```

---

## Self-Review (completed during planning)

- **Spec coverage:** §5 extraction → Tasks 6–8; §6 quality → Task 9; §7 canonical →
  Task 10; §8 synonyms → Task 11; §9 aspect → Task 12; §10 sentiment → Task 13; §11
  aggregate → Task 14; §12 lexicon → Task 3; §16 clause-split fix → Task 4 + back-compat
  Task 15; data model (§4) → Task 1; postag (§5) → Task 2; README (audit) → Task 16.
- **Placeholder scan:** every code step contains full code; cross-module coupling
  (aspect contract key `ambience`) is called out explicitly in Tasks 14–15.
- **Type consistency:** `Phrase` fields are used identically across tasks;
  `descriptor_tokens` (list) vs `descriptor` (str) kept distinct; `route_aspect`
  returns `(aspect, conf)`; `aggregate.build` returns the keyword contract dict.

**Known execution-time confirmations (flagged in tasks, not blockers):**
1. PyThaiNLP stative-verb tag strings → adjust `postag.STATIVE_TAGS` (Task 2/8).
2. `ASPECT_LEXICON` key is `ambience` (not `atmosphere`) → `_ASPECT_KEY` map (Task 15).
```
