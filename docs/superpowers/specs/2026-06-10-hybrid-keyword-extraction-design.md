# Hybrid Keyword Extraction (Rule-based + Claude) + Engine Comparison

**Date:** 2026-06-10
**Status:** Approved (design) — pending spec review
**Branch:** `feat/review-insight-phrase-extraction`
**Author:** suthi04 (with Claude)
**Supersedes/extends:** [2026-06-09-review-insight-phrase-extraction-design.md](2026-06-09-review-insight-phrase-extraction-design.md)

---

## 1. Problem & Goal

The phrase pipeline shipped (see the 2026-06-09 design) but the keyword output is
still weak in practice. Running the live pipeline on the 30-review demo set shows
three concrete defects:

1. **Fragmentation** — almost every phrase has `count = 1`. Synonymous opinions
   (`ไม่ค่อยประทับใจ`, `อาหารผิดหวัง`, `อาหารงั้นๆ`, `อาหารแย่`) sit as separate
   one-offs, so no "top issue" stands out. `รอนาน` appears in 3 reviews yet shows
   as three separate `count = 1` entries.
2. **Over-synthesis / lost original wording** — the canonical stage strips
   intensifiers (`บริการดีมาก` → `บริการดี`) and prepends head nouns even when the
   span already reads naturally, producing awkward forms like `บริการรอนาน`.
3. **Limited vocabulary** — extraction only recognises words curated in
   `core/lexicon.py`; unseen slang (`แซ่บ`, `ฟิน`, `จิ้มจุ่ม`) is silently dropped.

**Goal:** make the dashboard keyword/phrase output genuinely useful — opinion
phrases that read like real review wording, grouped by aspect + sentiment, with
counts that aggregate repeats **without destroying the original text** — and add a
second, modern extraction engine (Claude / LLM-based ABSA) alongside the rule-based
one, with a head-to-head comparison.

### Product intent (from this round of brainstorming)
> Keep opinion **phrases** as the primary unit (`บริการดีมาก`, `รออาหารนาน`,
> `พนักงานสุภาพ`), group by aspect + sentiment, aggregate afterwards **without
> losing the valuable original text**.

---

## 2. Decisions & constraint changes

This round **revises two constraints** from the 2026-06-09 design. Both are
deliberate, user-approved reversals:

| Prior constraint | New decision | Why |
|---|---|---|
| Intensifiers/fillers **stripped** from canonical phrase | **Display keeps intensifiers** (`บริการดีมาก`); only fillers dropped | User wants fidelity to original wording; `ดีมาก` carries real signal |
| "No new heavy ML / large deps; WangchanBERTa only" | **Add an optional Claude (LLM) extraction engine** | Project proposal is a draft; will be re-confirmed with the advisor. Added as an *optional, fallback-guarded* engine + a **comparison study**, not a replacement — the rule-based core remains the explainable baseline. |

### Academic framing (governing)
The rule-based pipeline stays the **primary, defensible contribution** (transparent,
offline, explainable at defense). The LLM engine is positioned as a **comparison
baseline / enhancement**, so the natural advisor question — "how is this different
from just sending reviews to an AI?" — is answered with measured results:
rule-based vs LLM on the existing labelled data, trading accuracy against cost,
transparency, and offline capability.

### Separation of concerns (unchanged)
`display` (what the user reads) is decoupled from `agg_key` (how repeats are
grouped). Normalisation happens **only** for counting, never for display.

---

## 3. Architecture overview

```
                         ┌─────────────── extract_engine = "rule" (default) ───────────────┐
reviews ──> preprocess ──┤  extract → quality → canonical → synonyms → route → sentiment    ├──> aggregate.build ──> keywords contract ──> dashboard
                         └─────────────── extract_engine = "llm" (opt-in, key present) ─────┘
                                          llm_extract  ──────────────────────────────────────┘ (maps into the same Phrase / contract)

fallback: engine="llm" but no ANTHROPIC_API_KEY or API error  ->  silently use "rule"  (mirrors WangchanBERTa -> lexicon)
```

Both engines emit the **same** `keywords` contract
(`{aspect: {positive|neutral|negative: [{word, count}]}}`), so `insights.py`,
`db/database.py`, `app.py`, and the dashboard template need **no contract change**.

---

## 4. Phase 1 — Rule-based quality (no API key required)

Ships value immediately and is the comparison baseline.

### 4.1 `core/phrases/model.py`
Add two fields to `Phrase` (existing fields untouched, so other stages keep working):
- `display: str` — natural readable phrase from the source span (intensifiers kept,
  original token order, only `FILLERS` removed).
- `agg_key: str` — normalised grouping key (intensifier-stripped canonical + synonym
  concept). Used only by `aggregate`.

### 4.2 `core/phrases/canonical.py`
- Build `display` by joining the matched span tokens in original order:
  `head_noun` (only if it appeared in the source) + negator + descriptor tokens +
  **intensifiers**, dropping only `FILLERS`. Examples: `บริการ ดี มาก` →
  `บริการดีมาก`; `รอ นาน` → `รอนาน`; `ไม่ ประทับใจ` → `ไม่ประทับใจ`.
- **Stop over-synthesising head nouns.** Synthesise `อาหาร`/`บริการ`/`บรรยากาศ`
  onto a phrase **only** when it is a *bare lone descriptor* (single descriptor
  token, no noun in the source) with a high-confidence aspect (`อร่อย` →
  `อาหารอร่อย`). If the span already contains a head noun, is a compound, or already
  reads naturally, keep the source wording — no `บริการรอนาน`.
- `agg_key` keeps the current normalised `canonical` behaviour (strip intensifiers;
  synonym concept applied in stage 4).

### 4.3 `core/phrases/aggregate.py`
- Group occurrences by `(aspect, sentiment, agg_key)` → `รอนาน × 3` collapses to one
  entry with `count = 3`.
- **Displayed label = the most frequent `display`** among the grouped occurrences
  (ties: shorter string, then lexicographic). Raises counts **and** preserves real
  original wording.
- Sort by `count` desc, then label; keep `TOP_N`.

### 4.4 `core/lexicon.py`
Conservatively add common missing descriptors/nouns (e.g. `แซ่บ`, `จิ้มจุ่ม`,
`ฟิน` if absent, a few high-frequency sensory words). Document the vocabulary
**limitation** in the README as an explicit, known constraint (a plus at defense).

### 4.5 Review fixes folded in (from the code review)
1. `sentiment.classify_phrase` — reuse the already-computed `clause["sentiment"]`
   for the ambiguous branch instead of re-invoking the model per phrase (latency).
2. `config.SECRET_KEY` — log a warning when falling back to a random key; document
   that production must set `SECRET_KEY` (multi-worker sessions otherwise break).
3. `core/pipeline._phrase_pipeline` — wrap per-review work in try/except so one
   malformed clause cannot 500 the whole analysis.
4. README — correct the sentiment methodology (phrase's own polarity wins; context
   only for ambiguous) and document the `topics` output.

---

## 5. Phase 2 — Claude (LLM) extraction engine

### 5.1 New module `core/phrases/llm_extract.py`
- Uses the official **Anthropic Python SDK** (`anthropic`), imported lazily/optional
  the same way `pythainlp` is, so the app still runs when the package is absent.
- **Structured output** via a JSON schema (`output_config.format`): each review →
  `[{ "phrase": str, "aspect": "food"|"service"|"ambience", "sentiment": "positive"|"neutral"|"negative" }]`.
- **Batch** multiple reviews per request to cut cost/latency; map results back to
  reviews by index.
- Map each item into the existing `Phrase`/contract path and reuse
  `aggregate.build` so the dashboard contract is identical.
- Model id from env `ANTHROPIC_MODEL`, default `claude-opus-4-8`; README notes
  `claude-haiku-4-5` as the low-cost option. Default thinking adaptive is
  unnecessary for this extraction; use a single structured call.

### 5.2 Engine selection & fallback (`config.py` + `core/pipeline.py`)
- Add `extract_engine` to settings (`get_settings()`), values `"rule"` (default) |
  `"llm"`; surfaced in the settings page like `use_model`.
- `_phrase_pipeline` chooses the engine. If `extract_engine == "llm"` **and** a key
  is available **and** the SDK import succeeds → call `llm_extract`; on any failure
  (no key, import error, API error) → **silently fall back to the rule-based path**
  and record an engine label (mirrors the WangchanBERTa→lexicon pattern, including a
  one-time warning).
- Backward compatibility: default stays `"rule"`, so existing behaviour and saved
  analyses are unaffected.

### 5.3 Security / cost notes
- API key only from env (`ANTHROPIC_API_KEY`); never committed, never logged.
- Cost is bounded (short reviews, batched); README states the rough per-analysis cost
  and that the LLM path is opt-in.

---

## 6. Phase 3 — Engine comparison (academic deliverable)

`scripts/compare_engines.py`:
- Runs both engines over `data/labeled_reviews.json` and reports metrics:
  aspect/sentiment agreement between engines, and accuracy against the existing
  sentiment labels where applicable; emits a small table (and/or CSV).
- The rule-based half runs with no key; the LLM half runs only when a key is present
  (skips with a clear message otherwise).
- Output is the evidence that answers the "why not just use AI" question.

---

## 7. Testing (TDD — write tests first, each phase)

- **Phase 1**
  - `display` retains intensifiers (`บริการดีมาก` not `บริการดี`).
  - `aggregate` merges `รอนาน × 3` into `count = 3`.
  - No `บริการรอนาน` synthesis; bare `อร่อย` still becomes `อาหารอร่อย`.
  - Aggregated label equals a representative original `display`.
  - `classify_phrase` reuses `clause["sentiment"]` (assert no extra model call).
  - `_phrase_pipeline` survives a malformed clause without raising.
  - `run_analysis` output contains a well-shaped `topics` key.
  - Newly added lexicon words are extracted.
- **Phase 2**
  - `llm_extract` parses a mocked schema response into the contract correctly.
  - No `ANTHROPIC_API_KEY` (or import failure) → pipeline falls back to rule output.
  - **No live API calls in tests** — the SDK is mocked.
- **Phase 3**
  - `compare_engines` runs the rule-based half headless and produces a metrics table;
    LLM half is skipped/mocked.

---

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| LLM dependency breaks offline/demo mode | Optional import + automatic fallback to rule-based; default engine stays `"rule"` |
| Advisor rejects adding an LLM | Rule-based remains a complete, standalone system; LLM is additive and removable |
| Cost / no key now | Phase 1 delivers value with no key; Phase 2 code is built but inert until a key is set |
| Non-deterministic LLM output | Structured JSON schema; fixed aspect/sentiment enums; comparison run documents variance |
| `display` vs `agg_key` divergence bugs | Unit tests pin both the merge key and the displayed label |
| Backward compatibility of saved analyses | Contract unchanged; default engine unchanged; new keys additive and template-guarded |

---

## 9. Out of scope

- Changing the dashboard `keywords`/`topics` contract shape.
- Replacing WangchanBERTa sentiment.
- A new gold-standard phrase/aspect dataset (comparison reuses existing labels +
  qualitative examples).
- Managed Agents / multi-call agentic flows — a single structured extraction call is
  sufficient.
