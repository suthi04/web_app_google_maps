# Switch the LLM Extraction Engine from Claude (Anthropic) to Gemini (Google)

**Date:** 2026-06-10
**Status:** Approved (design) — pending spec review
**Branch:** `feat/review-insight-phrase-extraction`
**Author:** suthi04 (with Claude)
**Supersedes/extends:** [2026-06-10-hybrid-keyword-extraction-design.md](2026-06-10-hybrid-keyword-extraction-design.md) (§5 Claude engine)

---

## 1. Problem & Goal

The optional LLM phrase-extraction engine currently calls **Anthropic Claude**
([core/phrases/llm_extract.py](../../../core/phrases/llm_extract.py)), which requires
a paid `ANTHROPIC_API_KEY`. For an undergraduate-thesis budget we want the LLM engine
to use **Google Gemini**, which has a usable **free tier** (Google AI Studio key).

**Goal:** replace Claude with Gemini as the `extract_engine = "llm"` implementation —
**same dashboard contract, same fallback behaviour, same academic rule-vs-LLM
comparison** (the "LLM" side is now Gemini). No other behaviour changes.

### Governing decision (from brainstorming)
**Replace, do not add a third engine.** Gemini takes over the `"llm"` slot entirely;
Claude support is removed. Chosen because the user is switching for cost, has no Claude
key, and a single LLM engine keeps the design and the comparison study simple (YAGNI).

---

## 2. Constraints

- Keep the **existing `extract_engine` values** `"rule" | "llm"` — do **not** rename to
  `"gemini"`. Existing `data/settings.json` and saved-analysis `extract_engine` fields
  carry `"llm"`; renaming would break them and require migration for no real benefit.
- Keep the **dashboard `keywords` contract** and the `Phrase` → `aggregate.build` path
  unchanged, so `app.py`, `db/database.py`, the template, and `eval` need no contract change.
- Keep **automatic fallback to rule-based** when the engine is unavailable or errors
  (mirrors the WangchanBERTa → lexicon pattern).
- The LLM SDK must be **optional/lazy-imported** so the app still runs (demo + rule mode)
  without it installed — exactly as `anthropic` is today.
- **No live API calls in tests** — the SDK client is mocked.

---

## 3. Architecture overview

```
extract_engine = "rule" (default) ─► rule pipeline (unchanged)
extract_engine = "llm"  + GEMINI_API_KEY + google-genai installed
        ─► llm_extract.extract_all(reviews)  [now calls Gemini]
                ─► Gemini generate_content (JSON mode + response_schema)
                ─► _to_contract()  ─► aggregate.build()  ─► same keywords contract
fallback: engine "llm" but no key / SDK missing / API error ─► silently use rule
```

Only the **inside** of `llm_extract.py` changes provider; everything around it is identical.

---

## 4. Detailed changes (file-by-file)

### 4.1 `core/phrases/llm_extract.py` (rewrite internals; keep filename + public API)
The module stays the generic "LLM engine" with the same public surface
(`available()`, `extract_all(reviews)`, `_to_contract(payload)`), so
[core/pipeline.py](../../../core/pipeline.py) imports are unchanged.

- Replace `import anthropic` usage with the **Google GenAI SDK**: `from google import genai`
  (and `from google.genai import types`), imported **lazily** inside `available()` /
  `_client()` so absence does not break the app.
- `available()` → `True` only if `config.get_gemini_api_key()` is set **and**
  `google.genai` is importable (same two-gate logic as today).
- `_client()` → `genai.Client(api_key=config.get_gemini_api_key())`.
- `extract_all(reviews)` → one batched `client.models.generate_content(...)` call with:
  - `model = config.GEMINI_MODEL`
  - `contents` = the existing `_build_prompt(reviews)` (one review per line, prefixed by index)
  - `config = types.GenerateContentConfig(system_instruction=_SYSTEM,
    response_mime_type="application/json", response_schema=_SCHEMA)`
  - parse `resp.text` with `json.loads`, then existing `_to_contract`.
- `_SYSTEM`, `_build_prompt`, `_to_contract`, `_ASPECT_KEY`, `_SENTS`, batch-by-index — **unchanged**.
- **Schema adaptation:** Gemini's `response_schema` accepts an OpenAPI-3 subset
  (`type`, `properties`, `required`, `items`, `enum`). It does **not** use
  `additionalProperties`. `_SCHEMA` is adapted to a Gemini-compatible dict (drop
  `additionalProperties`; keep the `food|service|ambience` and
  `positive|neutral|negative` enums and `required`). The contract (`reviews →
  [{index, phrases:[{phrase, aspect, sentiment}]}]`) is otherwise identical.

### 4.2 `config.py`
Replace the Anthropic block with a Gemini block (same shape as today):
- Remove `ANTHROPIC_MODEL` and `get_anthropic_api_key()`.
- Add `GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()`
  (read at import, like `MODEL_NAME`).
- Add `get_gemini_api_key()` → reads `GEMINI_API_KEY` **live** from env (so tests can
  patch it, same reason the Anthropic getter read live).

### 4.3 `requirements.txt`
- Remove `anthropic>=0.40`.
- Add `google-genai` (optional — only needed for the Gemini extraction engine), with the
  same "optional" comment style.

### 4.4 `.env.example`
- Replace the Claude block with:
  ```
  # ---------- ใช้ Gemini (LLM) สกัดวลีความเห็น (ทางเลือกเพิ่มเติม) ----------
  # ตั้ง GEMINI_API_KEY เพื่อเปิดเครื่องยนต์ Gemini (เลือกได้จากหน้า Settings)
  # ฟรีจาก Google AI Studio (aistudio.google.com); ไม่ตั้ง/เรียกพลาด -> fallback rule-based
  GEMINI_API_KEY=
  # โมเดล (ไม่บังคับ) — ค่าเริ่มต้น gemini-2.5-flash
  # GEMINI_MODEL=gemini-2.5-flash
  ```

### 4.5 `templates/settings.html`
- Radio label **"Claude (LLM)"** → **"Gemini (LLM)"**; description references
  `GEMINI_API_KEY` and the free tier; "ถ้าไม่มีจะใช้ rule-based อัตโนมัติ" kept.

### 4.6 `tests/test_llm_extract.py`
- `test_unavailable_without_key`: patch `GEMINI_API_KEY` empty → `available()` False.
- `test_parse_response_to_contract`: unchanged (pure `_to_contract`, provider-agnostic).
- `test_extract_all_uses_client_and_returns_contract`: mock the **genai** client so
  `client.models.generate_content(...).text` returns the JSON payload; assert the
  contract and that the client was called once. No live API calls.

### 4.7 Docs / wording
- [README.md](../../../README.md) §🤖 "เครื่องยนต์สกัดวลี": Claude → Gemini
  (env var, free-tier note, default model, fallback). Cost paragraph reworded for
  Gemini's free tier.
- [scripts/compare_engines.py](../../../scripts/compare_engines.py) docstring/flag help:
  "Claude" → "Gemini" (the `--llm` flag and `llm_extract.available()` gating are unchanged).

---

## 5. What does NOT change

`extract_engine` values (`rule`/`llm`), the `keywords`/`topics` contract,
`Phrase`/`_to_contract`/`aggregate.build`, the automatic fallback to rule, the
clause-level rule pipeline, sentiment (WangchanBERTa/lexicon), DB schema, export, and
the rule-vs-LLM comparison framing (the "LLM" engine is now Gemini).

---

## 6. Error handling & fallback (unchanged)

| Condition | Behaviour |
|---|---|
| `GEMINI_API_KEY` unset | `available()` False → pipeline uses rule-based |
| `google-genai` not installed | lazy import fails → `available()` False → rule-based |
| Gemini API error / bad JSON | `extract_all` raises → `_phrase_pipeline` catches → rule-based + one-time warning |
| Engine reported in result | `extract_engine = "llm"` only when Gemini actually ran; else `"rule"` |

---

## 7. Testing (TDD)

- Adapt the three existing `test_llm_extract.py` tests to the genai client (mocked).
- Keep the full suite green (`python -m unittest discover -s tests`).
- **Pin the exact `google-genai` call shape against the installed package / official docs
  during implementation** — do not guess SDK signatures. If the SDK is not installed in
  the dev environment, the mocked tests still pass (lazy import), and the real call path
  is verified once `google-genai` is installed.

---

## 8. Free-tier notes (for README)

- Get a key free at **Google AI Studio** (`aistudio.google.com`) → API key.
- Free tier has per-minute / per-day request limits; batching all reviews into one
  request per analysis keeps usage well within limits for this workload.
- Default model `gemini-2.5-flash` (fast + free-tier friendly); override via `GEMINI_MODEL`.

---

## 9. Out of scope

- Provider abstraction / keeping Claude as a selectable engine (explicitly rejected — replace).
- Changing the dashboard contract, sentiment engine, or the rule pipeline.
- Streaming, thinking/effort tuning, or multi-call agentic flows — a single structured
  `generate_content` call is sufficient.

---

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Gemini `response_schema` rejects Anthropic-style schema (`additionalProperties`) | Adapt `_SCHEMA` to the Gemini OpenAPI-subset form (drop `additionalProperties`, keep enums/required) |
| Free-tier rate limit hit | One batched request per analysis; document limits; fallback to rule on error |
| SDK signature differs from assumption | Verify against installed `google-genai` / docs during implementation (TDD), not from memory |
| Existing saved analyses / settings use `extract_engine:"llm"` | Value kept identical — no migration needed |
