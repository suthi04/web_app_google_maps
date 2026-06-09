# Review Insight — Phrase Extraction & Classification Redesign

**Date:** 2026-06-09
**Status:** Approved (design) — pending spec review
**Branch:** `feat/review-insight-phrase-extraction`
**Author:** suthi04 (with Claude)

---

## 1. Problem & Goal

InsightReview currently extracts **single words / weak bigrams** for its dashboard,
producing noisy, low-value output (`อาหาร`, `ดี`, `อร่อย`, `เมนู`) and frequently
misfiling them into the wrong aspect. The keyword stage cannot recover real Thai
review phrasing (idioms, stative-verb opinions, reversed order), and aspect
classification guesses at the clause level.

**Goal:** rebuild the keyword stage into a **Review Insight** pipeline that extracts
**meaningful, canonical opinion phrases** from Thai restaurant reviews and displays
them on the dashboard grouped by aspect and sentiment.

This is **not** a keyword-extraction system and **must not**:
- recommend or output single-word keywords,
- rely solely on word frequency,
- show phrases that lack enough context to be a business insight.

### Desired output (example)
Review: `อาหารอร่อยมากๆ รสชาติจัดจ้าน ถึงเครื่องทุกเมนู ... บรรยากาศดี ติดริมน้ำ เย็นสบาย ไม่ร้อน เมนูปลาคือสดจริง ราคาไม่แพง ปริมาณเยอะ ...`

| Aspect | Phrases |
|---|---|
| Food | อาหารอร่อย · รสชาติจัดจ้าน · ถึงเครื่อง · ปลาสด · ปริมาณเยอะ · ราคาไม่แพง |
| Atmosphere | บรรยากาศดี · ติดริมน้ำ · เย็นสบาย |

### Rejected output
`อาหาร`, `เมนู`, `ร้าน`, `ดี`, `อร่อย` (bare), `ชอบ`, `แนะนำ` — single words or
context-free phrases with no actionable business meaning.

---

## 2. Constraints (governing)

- **Undergraduate thesis project** — must be **explainable** during defense.
- Implementable in **a few weeks**.
- **Reuse WangchanBERTa** for sentiment; **no new heavy ML models / large deps**.
- Prefer **deterministic, maintainable** solutions.
- Only external NLP dependency is **PyThaiNLP** (already installed).
- Evaluation reuses the existing 60 sentiment labels (`data/labeled_reviews.json`);
  phrase/aspect quality demonstrated **qualitatively** with examples (no new gold set).

### Key product decisions (from brainstorming)
- **Phrase form = canonical opinion units** (head-noun + polarity word; intensifiers
  and fillers stripped), aggregated by count. Chosen because canonical forms
  aggregate into countable insights ("23 reviews praised อาหารอร่อย").
- **Taxonomy = 3 aspect cards** (Food / Service / Atmosphere). **Price folds into
  Food** (treated as a topic within Food, not a separate card).
- **Sentiment is per-phrase**, classified **in context**, separately from extraction.

---

## 3. Architecture Overview

Chosen: **Architecture 2 — POS-pattern chunking + lexicon validation**, a
deterministic hybrid. Rejected alternatives (recorded for the thesis):
- *Architecture 1 (lexicon adjacency only):* too low recall; can't produce
  `เข้มข้น`/`จัดจ้าน`/idioms. Retained as the **fallback strategy** inside Arch 2.
- *Architecture 3 (embeddings / KeyBERT):* black-box, needs labels we won't create,
  heavy deps — violates explainability + determinism. Documented as future work.

### Pipeline (8 stages → modules)

```
Review
  └─ preprocess (clauses + tokens + tokens_base)          core/preprocess.py  (refactor)
       │
  1. Phrase Extraction        POS tag + 3-strategy hybrid  core/postag.py            (new)
       │                                                   core/phrases/extract.py   (new)
  2. Phrase Quality Filtering  reject bare/meta/short       core/phrases/quality.py   (new)
       │
  3. Canonicalization          strip intensifiers/fillers, core/phrases/canonical.py (new)
       │                       reorder, gated P7 synthesis
  4. Synonym Aggregation       variant → concept (conservative) core/phrases/synonyms.py (new)
       │
  5. Aspect Classification     4-tier resolver             core/aspect.py            (refactor)
       │
  6. Sentiment Classification  per-occurrence, in context  core/sentiment.py         (extend)
       │
  7. Dashboard Aggregation     count by (aspect,sent,concept) core/phrases/aggregate.py (new)
       │
  Dashboard (unchanged contract)                           templates/dashboard.html
```

**Design principle:** every module is a pure function over an explicit `Phrase`
object and is unit-testable with **injected POS tags** — tests never depend on the
live tagger.

---

## 4. Core data object

```python
@dataclass
class Phrase:
    surface: str            # matched span, tokens joined ("อาหาร อร่อย มากๆ")
    canonical: str          # after stage 3 ("อาหารอร่อย")
    concept: str            # synonym-group key after stage 4; == canonical if ungrouped
    label: str              # human display label
    head_noun: str | None   # "อาหาร" | "ราคา" | None (synthesized/idiom)
    descriptor: str | None  # "อร่อย" | "ไม่แพง" | None
    pattern: str            # "P1".."P7" | "idiom" | "fallback"
    aspect: str | None      # food | service | atmosphere (stage 5)
    aspect_conf: str        # "high" | "low"
    sentiment: str | None   # positive | neutral | negative (stage 6, from context)
    clause: dict            # source clause {clean, tokens, tokens_base} for context sentiment
```

The `clause` back-reference is what keeps extraction and sentiment **separate**.

---

## 5. Stage 1 — Phrase Extraction (hybrid)

### `core/postag.py` (new)
Thin, swappable wrapper over PyThaiNLP.
- `pos_tag(tokens) -> list[(tok, tag)]` using `corpus="orchid_ud"`.
- If PyThaiNLP missing or raises → returns `(tok, "UNK")` for all tokens. **Never crashes.**
- `available() -> bool` so extraction can pick a strategy.

> **Thai-specific note:** opinion words (`อร่อย`, `สด`, `ดี`, `เข้มข้น`, `จัดจ้าน`)
> are **stative verbs**, tagged `VERB`/`VATT`, **not** `ADJ`. The chunk grammar's
> descriptor slot therefore targets stative VERB tags. The exact tag strings emitted
> by the installed PyThaiNLP version **must be confirmed during implementation** and
> centralized in one constant (`STATIVE_TAGS`).

### `core/phrases/extract.py` (new)
`extract(clause) -> list[Phrase]`. Three strategies applied per clause **in priority
order**, with span-overlap suppression (a consumed token is not reused):

| Order | Strategy | Behavior | Covers |
|---|---|---|---|
| A | **Phrase dictionary / idiom MWE** | longest-match against curated `IDIOMS` and known-good phrases | P6 — idioms POS can't parse |
| B | **POS chunk grammar** | patterns P1–P5 over POS tags (descriptor = stative VERB) | P1–P5 — the bulk |
| C | **Fallback adjacency rule** | when POS unavailable/UNK or B finds nothing: lexicon adjacency (known noun + known descriptor) = Architecture-1 behavior | safety net |

**Graceful degradation:** with PyThaiNLP off, strategies A + C keep the system
working (and the integration test runs in that mode).

#### Chunk grammar (descriptor = stative VERB)
| Pattern | POS skeleton | Example surface |
|---|---|---|
| P1 | `NOUN (ADV)* STATIVE` | อาหาร อร่อย มากๆ |
| P2 | `NOUN NEG STATIVE` | ราคา ไม่ แพง |
| P3 | `VERB (ADV)* STATIVE/ADV` | รอ นาน มาก |
| P4 | `STATIVE ADP NOUN` (reversed) | คุ้มค่า กับ ราคา |
| P5 | `NOUN STATIVE ADV(freq)` | คน เยอะ ตลอด |
| P7 | bare `STATIVE`, no noun | อร่อย / ดี → gated synthesis (stage 3) |

---

## 6. Stage 2 — Quality Filtering — `core/phrases/quality.py` (new)

`filter(phrases, clause_aspects) -> list[Phrase]`. Rejects:
- **Bare aspect noun** (no descriptor): `อาหาร`, `เมนู`, `ร้าน`.
- **Meta/recommendation verbs** (`META_VERBS = {ชอบ, แนะนำ, บอก, ...}`).
- **Too short / stopword-only / numeric** (`MIN_LEN`, `IGNORE`).
- **Bare descriptor (P7):** marked for synthesis; sets a **provisional aspect** +
  `aspect_conf` (needed by stage 3 synthesis, which runs before the stage-5 resolver):
  - `high` + provisional aspect if the descriptor is lexicon-bound to one aspect
    (`อร่อย`→food via `DESCRIPTOR_ASPECT_HINTS`/`DESCRIPTORS`) **or** the clause has
    exactly one aspect.
  - `low` if the descriptor is unbound **and** the clause has ≥2 aspects.

This stage decides *worthiness only* — it never touches sentiment. The provisional
aspect is finalized in stage 5 (for synthesized P7 phrases the head noun now exists,
so the stage-5 head-noun mapping yields the same aspect — no contradiction).

---

## 7. Stage 3 — Canonicalization — `core/phrases/canonical.py` (new)

`canonicalize(phrase) -> Phrase` (sets `.canonical`):
- Strip `INTENSIFIERS = {มาก, มากๆ, สุดๆ, จริง, จริงๆ, เลย, ๆ}`.
- Drop `FILLERS = {คือ, ที่, อะ}`.
- **Reorder P4:** `คุ้มค่า กับ ราคา` → `ราคาคุ้มค่า`.
- **Gated P7 synthesis (hallucination guard):**
  - `aspect_conf == "high"` → prepend `ASPECT_HEAD_NOUN[aspect]`
    (`อร่อย`→`อาหารอร่อย`, `ดี`@atmosphere→`บรรยากาศดี`, `คึกคัก`@atmosphere→`บรรยากาศคึกคัก`).
  - `aspect_conf == "low"` → **reject the phrase**.
- **Preserve negation** (`ราคาไม่แพง` keeps `ไม่`) so antonyms never collapse.

`ASPECT_HEAD_NOUN = {food:"อาหาร", service:"บริการ", atmosphere:"บรรยากาศ"}`.

---

## 8. Stage 4 — Synonym Aggregation — `core/phrases/synonyms.py` (new)

**Conservative, opt-in, dictionary-driven.** Default behavior is **identity**
(`concept == canonical`). Aggregation happens **only** via a curated whitelist.

### Aggregation policy
Merge two phrases **only if all hold**:
1. same **business lever** (e.g., price affordability, service speed),
2. same **orientation** (antonyms never merge), and
3. a manager would **act identically** on them.

**Do NOT merge distinct sensory/quality descriptors** even when all positive —
`อร่อย`, `จัดจ้าน`, `เข้มข้น`, `ถึงเครื่อง` are **separate concepts**, each its own
insight.

```python
SYNONYM_GROUPS = {
  "price_good": {"label": "ราคาคุ้มค่า", "aspect": "food",
                 "members": {"คุ้มค่า", "ราคาดี", "ราคาไม่แพง", "ราคาเหมาะสม", "ราคาโอเค"}},
  "price_bad":  {"label": "ราคาแพง", "aspect": "food",
                 "members": {"ราคาแพง", "แพงไป", "ไม่คุ้ม", "ไม่คุ้มค่า"}},
  "wait_long":  {"label": "รอนาน", "aspect": "service",
                 "members": {"รอนาน", "มาช้า", "อาหารมาช้า", "เสิร์ฟช้า"}},
  # literal paraphrases only (same wording):
  "taste_good": {"label": "รสชาติดี", "aspect": "food",
                 "members": {"รสชาติดี", "รสดี"}},
}
# NOT grouped (each its own concept): อร่อย, จัดจ้าน, เข้มข้น, ถึงเครื่อง,
#   ติดริมน้ำ, เย็นสบาย, คึกคัก, เงียบสงบ, คนเยอะ, ปริมาณเยอะ, ปลาสด, ...
```

- Groups are **meaning-level**, so `price_good` vs `price_bad` stay separate.
- Groups **carry no sentiment** — orientation is for grouping only; the displayed
  sentiment per occurrence is decided in stage 6.
- `to_concept(canonical) -> (key, label)`; no match → `(canonical, canonical)`.

---

## 9. Stage 5 — Aspect Classification — `core/aspect.py` (refactor)

Aspect routing is **not** noun-primary. `route_aspect(phrase, clause_aspects) ->
(aspect, conf)` resolves in this order:

1. **Idiom / curated mapping** — `phrase.pattern == "idiom"` → `IDIOMS[...]["aspect"]`;
   **or** a matched synonym concept's declared `aspect` (curated concepts are as
   authoritative as idioms) (conf high).
2. **Head Noun Mapping** — `head_noun in ASPECT_NOUNS` → that aspect (conf high).
   (`ราคา`→food per the Price-into-Food decision.)
3. **Clause Context** — resolve **only** when the clause has exactly one detected
   aspect → use it (conf high). If the clause has ≥2 aspects, do **not** guess here;
   fall through to tier 4 (consistent with the hallucination-guard philosophy).
4. **Fallback Rules** — `DESCRIPTOR_ASPECT_HINTS[descriptor]` (conf medium); else
   `uncategorized` → excluded from the aspect panels.

`DESCRIPTOR_ASPECT_HINTS` (curated) routes **noun-less** phrases and also feeds
clause-context detection:
```python
DESCRIPTOR_ASPECT_HINTS = {
  "เย็นสบาย": "atmosphere", "คึกคัก": "atmosphere", "เงียบสงบ": "atmosphere",
  "ริมน้ำ": "atmosphere", "โล่ง": "atmosphere", "อึดอัด": "atmosphere",
  "รวดเร็ว": "service", "ช้า": "service", ...
}
```

Source-of-truth cleanup (long-standing smell): split today's `ASPECT_LEXICON` into
**`ASPECT_NOUNS`** (head noun → aspect) and **`DESCRIPTORS`** (polarity words), so the
two jobs stop overlapping.

---

## 10. Stage 6 — Sentiment Classification — `core/sentiment.py` (extend)

**Independent of extraction** (the central separation requirement).
`classify_phrase(phrase) -> "positive"|"neutral"|"negative"`:
- **Primary (model on):** WangchanBERTa on the phrase's **source clause** (context),
  not the bare phrase. So `คนเยอะ` / `คนแน่น` / `คึกคัก` get positive **or** negative
  per the surrounding text — never from a fixed phrase polarity.
- **Backstop (model off / demo):** negation-aware descriptor polarity; ambiguous
  phrases default `neutral`.
- Each occurrence is classified **independently**, then aggregated — so one concept
  may appear in both Positive and Negative columns with different counts.

---

## 11. Stage 7 — Dashboard Aggregation — `core/phrases/aggregate.py` (new)

- Group occurrences by `(aspect, sentiment, concept)`; `count` = occurrences;
  `word` = group `label`.
- Rank within a cell by count → specificity (phrase > bare) → length.
- Take `TOP_N` (≈6 per cell).
- **Output keeps the existing contract** so dashboard/template/DB/export are
  structurally unchanged:
  ```
  {food:{positive:[{word,count}], neutral:[...], negative:[...]},
   service:{...}, atmosphere:{...}}
  ```
- `extract_topics` ("ลูกค้าพูดถึงบ่อย") is retained as-is.

---

## 12. Lexicon / data — `core/lexicon.py` (expanded)

Plain Python dicts (deterministic, diff-friendly, no file IO):
`ASPECT_NOUNS`, `DESCRIPTORS` (+polarity), `IDIOMS {phrase → {canonical, aspect}}`,
`DESCRIPTOR_ASPECT_HINTS`, `INTENSIFIERS`, `FILLERS`, `META_VERBS`,
`ASPECT_HEAD_NOUN`, `SYNONYM_GROUPS`.

Seed `IDIOMS`: `ติดริมน้ำ`→{ริมน้ำ, atmosphere}, `ถึงเครื่อง`→{ถึงเครื่อง, food},
`มาไว`→{มาไว, service}.

---

## 13. Error handling & graceful degradation

| Condition | Behavior |
|---|---|
| PyThaiNLP missing / tagger error | strategy C fallback; never crash |
| WangchanBERTa unavailable | lexicon sentiment backstop (existing pattern) |
| Low aspect confidence (P7) | drop phrase (no hallucinated insight) |
| Empty clause / zero candidates | skip cleanly |

---

## 14. Testing

- **Unit, tagger-independent** (inject POS tags):
  - extract: P1–P7, idiom longest-match, fallback path, overlap suppression.
  - quality: each reject rule; confidence gating (high vs low).
  - canonical: intensifier/filler strip, P4 reorder, gated synthesis, negation kept.
  - synonyms: price merge; **antonym separation**; distinct descriptors NOT merged
    (`อร่อย`/`จัดจ้าน`/`เข้มข้น` stay separate).
  - aspect: 4-tier resolution incl. noun-less atmosphere via hints.
- **Separation test:** `คนเยอะ` in positive vs negative context → different
  sentiment, same concept.
- **Golden set:** ~10 real reviews → expected canonical phrases (regression).
- **Integration:** existing demo/lexicon smoke test, updated to the new contract.
- Suite stays runnable via `python -m unittest discover -s tests`.

---

## 15. Evaluation (thesis)

- **Sentiment:** keep `eval/evaluate.py` on the 60-label set (Accuracy/F1/κ).
- **Phrase & aspect quality:** qualitative — curated example reviews → extracted
  phrases, with screenshots and a short error analysis (false merges, mis-routes,
  dropped synthesis). No new gold set required.

---

## 16. Backward compatibility & blast radius

- `pipeline.run_analysis` output **keys unchanged**; DB payload, templates, export,
  and `eval` are structurally untouched.
- `core/keyphrase.py` and `core/keywords.py` bucketing are **superseded** by
  `core/phrases/*`; removed only after parity tests pass.
- `core/clause.py` clause-split bug (substring `แต่` mangling `ตกแต่ง`) is fixed as
  part of this work by splitting on the **tokenized** stream.

---

## 17. Implementation phasing (suggested)

1. `postag.py` + `STATIVE_TAGS` confirmation; clause-split-on-tokens fix.
2. `lexicon.py` split + new dicts (idioms, hints, intensifiers, synonyms).
3. `phrases/extract.py` (A/B/C) with injected-tag unit tests.
4. `phrases/quality.py` + `phrases/canonical.py` (incl. gated synthesis).
5. `phrases/synonyms.py` (conservative whitelist).
6. `aspect.py` 4-tier resolver; `sentiment.classify_phrase`.
7. `phrases/aggregate.py`; wire `pipeline.py`; parity + integration tests.
8. Remove superseded code; update README.

---

## 18. Future work (out of scope)

- Architecture 3: WangchanBERTa-embedding aspect routing / KeyBERT candidate ranking
  to lift recall on unseen vocabulary.
- Expand the curated dictionaries from real labeled data.
- A small phrase/aspect gold set for quantitative phrase evaluation.

---

## 19. Open questions

- Exact PyThaiNLP POS tagset/strings for stative verbs (confirm at impl).
- Whether curated dicts should later migrate to `data/*.json` for non-dev editing
  (kept in `lexicon.py` for now — simpler, testable, no IO).
```
