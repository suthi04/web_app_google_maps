# Gemini Extraction Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Anthropic Claude phrase-extraction engine with Google Gemini (free tier) while keeping `extract_engine="llm"`, the dashboard contract, and the rule fallback unchanged.

**Architecture:** Only the *internals* of `core/phrases/llm_extract.py` change provider (anthropic → google-genai). `config.py` swaps `ANTHROPIC_*` for `GEMINI_*`. The public surface (`available()`, `extract_all()`, `_to_contract()`), the `Phrase`→`aggregate.build` contract, and the silent fallback to rule-based all stay identical.

**Tech Stack:** Python 3, Flask, `google-genai` SDK (lazy/optional import), `unittest` (stdlib), Gemini JSON-mode (`response_mime_type` + `response_schema`).

**Spec:** [docs/superpowers/specs/2026-06-10-gemini-extraction-engine-design.md](../specs/2026-06-10-gemini-extraction-engine-design.md)

**Conventions for this repo:**
- Tests run with **`python -m unittest`** (NOT pytest).
- Commit messages end with: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- Work on branch `feat/review-insight-phrase-extraction` (already checked out).

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `config.py` | central env config | Modify: add `GEMINI_MODEL` + `get_gemini_api_key()`; later remove `ANTHROPIC_MODEL` + `get_anthropic_api_key()` |
| `core/phrases/llm_extract.py` | LLM engine (generic name, now Gemini inside) | Modify: swap provider internals; keep public API |
| `tests/test_config_gemini.py` | lock Gemini config behaviour | Create |
| `tests/test_llm_extract.py` | LLM engine unit tests (mocked client) | Modify: mock genai instead of anthropic |
| `requirements.txt` | deps | Modify: `anthropic` → `google-genai` |
| `.env.example` | config template | Modify: Claude block → Gemini block |
| `templates/settings.html` | engine picker UI | Modify: "Claude (LLM)" → "Gemini (LLM)" |
| `README.md` | docs | Modify: §🤖 Claude → Gemini; test count 133 → 136 |
| `scripts/compare_engines.py` | rule-vs-LLM harness | Modify: docstring/flag wording Claude → Gemini |

---

## Task 1: Add Gemini settings to config (keep Anthropic for now)

Adding (not removing) keeps the suite green while `llm_extract` still uses Anthropic.

**Files:**
- Create: `tests/test_config_gemini.py`
- Modify: `config.py` (add after the Anthropic block ~line 53-56, and add a getter after `get_extract_engine()`)

- [ ] **Step 1: Write the failing test**

Create `tests/test_config_gemini.py`:

```python
"""GEMINI_MODEL มีค่า default + get_gemini_api_key() อ่านสดจาก env (patch ได้)"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


class TestGeminiConfig(unittest.TestCase):
    def test_default_model(self):
        self.assertEqual(config.GEMINI_MODEL, "gemini-2.5-flash")

    def test_key_read_live_from_env(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-123"}, clear=False):
            self.assertEqual(config.get_gemini_api_key(), "test-key-123")

    def test_key_empty_when_unset(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False):
            self.assertEqual(config.get_gemini_api_key(), "")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_config_gemini -v`
Expected: FAIL — `AttributeError: module 'config' has no attribute 'GEMINI_MODEL'`

- [ ] **Step 3: Add the Gemini config block**

In `config.py`, immediately after the Anthropic block (the line `ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8").strip()` and its comment), add:

```python
# ---- Google Gemini (เครื่องยนต์สกัดวลี LLM — ทางเลือก opt-in, ฟรีจาก AI Studio) ----
# โมเดลอ่านตอน import; API key อ่านสดผ่าน get_gemini_api_key() (เผื่อ patch ใน test)
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()
```

At the end of `config.py`, after `get_anthropic_api_key()`, add:

```python
def get_gemini_api_key() -> str:
    """API key ของ Gemini (อ่านสดจาก env) — ว่าง = เครื่องยนต์ LLM ปิด/ไม่พร้อมใช้"""
    return os.environ.get("GEMINI_API_KEY", "").strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_config_gemini -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add tests/test_config_gemini.py config.py
git commit -m "feat(config): add GEMINI_MODEL + get_gemini_api_key()

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Swap `llm_extract.py` internals to Gemini (rewrite + tests)

**Files:**
- Modify: `core/phrases/llm_extract.py` (full rewrite of internals; public API unchanged)
- Modify: `tests/test_llm_extract.py` (mock genai client instead of anthropic)

- [ ] **Step 1: Rewrite the test for a mocked genai client**

Replace the entire contents of `tests/test_llm_extract.py` with:

```python
"""Gemini extraction maps a (mocked) structured response into the dashboard contract,
and reports unavailable when there is no API key. No real API calls are made."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.phrases import llm_extract


class TestLLMExtract(unittest.TestCase):
    def test_unavailable_without_key(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False):
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
        import json
        payload = {"reviews": [{"index": 0, "phrases": [
            {"phrase": "บริการดีมาก", "aspect": "service", "sentiment": "positive"}]}]}
        fake_resp = mock.Mock()
        fake_resp.text = json.dumps(payload)
        fake_client = mock.Mock()
        fake_client.models.generate_content.return_value = fake_resp
        with mock.patch.object(llm_extract, "_client", return_value=fake_client):
            out = llm_extract.extract_all([{"text": "บริการดีมาก"}])
        self.assertEqual(out["service"]["positive"][0]["word"], "บริการดีมาก")
        fake_client.models.generate_content.assert_called_once()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_llm_extract -v`
Expected: FAIL — `test_extract_all_uses_client_and_returns_contract` fails because the current `extract_all` calls `client.messages.create` (anthropic), not `client.models.generate_content`.

- [ ] **Step 3: Rewrite `core/phrases/llm_extract.py`**

Replace the entire file with:

```python
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

_SYSTEM = (
    "You extract opinion phrases from Thai restaurant reviews for a dashboard. "
    "For each review, return the concrete opinion phrases a customer expressed, in "
    "the customer's own wording (keep intensifiers like มาก). Classify each phrase "
    "into aspect food|service|ambience and sentiment positive|neutral|negative. "
    "Price/value belongs to food. Do not invent phrases not supported by the text."
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
```

- [ ] **Step 4: Run the LLM tests to verify they pass**

Run: `python -m unittest tests.test_llm_extract -v`
Expected: PASS (3 tests). The mocked `_client` means no `google` import is exercised.

- [ ] **Step 5: Run the full suite to confirm no regressions**

Run: `python -m unittest discover -s tests`
Expected: `OK`. (`pipeline._phrase_pipeline` still falls back to rule when `available()` is False, which it is without a key/SDK — integration tests stay green.)

- [ ] **Step 6: Commit**

```bash
git add core/phrases/llm_extract.py tests/test_llm_extract.py
git commit -m "feat(llm): swap extraction engine from Claude to Gemini

google-genai (lazy import), JSON-mode + response_schema; public API,
_to_contract, batch-by-index, and rule fallback unchanged.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Remove now-unused Anthropic config + swap the dependency

`llm_extract` no longer touches Anthropic, so its config + dep can go.

**Files:**
- Modify: `config.py` (remove `ANTHROPIC_MODEL` + comment, remove `get_anthropic_api_key()`)
- Modify: `requirements.txt`

- [ ] **Step 1: Remove the Anthropic config**

In `config.py`, delete the Anthropic comment + `ANTHROPIC_MODEL` line:

```python
# ---- Anthropic (เครื่องยนต์สกัดวลี Claude — ทางเลือก opt-in) ----
# โมเดลอ่านตอน import (เหมือน MODEL_NAME); ส่วน API key อ่านสดทุกครั้งผ่าน
# get_anthropic_api_key() เพราะ key อาจถูกตั้ง/แก้หลัง import ในบางบริบท (เช่นเทสต์)
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8").strip()
```

and delete the function:

```python
def get_anthropic_api_key() -> str:
    """API key ของ Claude (อ่านสดจาก env) — ว่าง = เครื่องยนต์ LLM ปิด/ไม่พร้อมใช้"""
    return os.environ.get("ANTHROPIC_API_KEY", "").strip()
```

- [ ] **Step 2: Swap the dependency in `requirements.txt`**

Replace the line:

```
anthropic>=0.40    # optional — only needed for the Claude (LLM) extraction engine
```

with:

```
google-genai>=1.0  # optional — only needed for the Gemini (LLM) extraction engine
```

- [ ] **Step 3: Verify no stray Anthropic references remain in Python**

Run: `git grep -n "anthropic\|ANTHROPIC\|claude" -- "*.py"`
Expected: **no matches** in `*.py` (README/spec wording is handled in Task 4).

- [ ] **Step 4: Run the full suite**

Run: `python -m unittest discover -s tests`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add config.py requirements.txt
git commit -m "refactor: drop unused Anthropic config + dependency

Replace anthropic with google-genai in requirements; remove
ANTHROPIC_MODEL / get_anthropic_api_key now that llm_extract uses Gemini.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Update docs & UI text (Claude → Gemini)

No code logic; verify the suite stays green and the test count is accurate.

**Files:**
- Modify: `.env.example`
- Modify: `templates/settings.html`
- Modify: `README.md` (§🤖 + test count)
- Modify: `scripts/compare_engines.py` (docstring + flag help)

- [ ] **Step 1: `.env.example` — replace the Claude block**

Replace:

```
# ---------- ใช้ Claude (LLM) สกัดวลีความเห็น (ทางเลือกเพิ่มเติม) ----------
# ตั้ง ANTHROPIC_API_KEY เพื่อเปิดเครื่องยนต์ Claude (เลือกได้จากหน้า Settings)
# ถ้าไม่ตั้งค่านี้ หรือเรียก API ไม่สำเร็จ ระบบจะ fallback กลับ rule-based อัตโนมัติ
ANTHROPIC_API_KEY=

# โมเดล (ไม่บังคับ) — ค่าเริ่มต้น claude-opus-4-8;
# ใช้ claude-haiku-4-5 สำหรับตัวเลือกที่ค่าใช้จ่ายต่ำกว่า
# ANTHROPIC_MODEL=claude-opus-4-8
```

with:

```
# ---------- ใช้ Gemini (LLM) สกัดวลีความเห็น (ทางเลือกเพิ่มเติม) ----------
# ตั้ง GEMINI_API_KEY เพื่อเปิดเครื่องยนต์ Gemini (เลือกได้จากหน้า Settings)
# ขอ key ฟรีที่ Google AI Studio (aistudio.google.com)
# ถ้าไม่ตั้งค่านี้ หรือเรียก API ไม่สำเร็จ ระบบจะ fallback กลับ rule-based อัตโนมัติ
GEMINI_API_KEY=

# โมเดล (ไม่บังคับ) — ค่าเริ่มต้น gemini-2.5-flash
# GEMINI_MODEL=gemini-2.5-flash
```

- [ ] **Step 2: `templates/settings.html` — relabel the LLM radio**

Replace:

```html
        <label class="radio-card {{ 'sel' if s.extract_engine == 'llm' }}">
          <input type="radio" name="extract_engine" value="llm" {{ 'checked' if s.extract_engine == 'llm' }}>
          <div class="rc-body">
            <div class="rc-title">Claude (LLM) <span class="rc-tag rec">แม่นยำกว่า</span></div>
            <div class="rc-desc">แม่นกว่าในรีวิวภาษาธรรมชาติ — ต้องตั้ง ANTHROPIC_API_KEY (ถ้าไม่มีจะใช้ rule-based อัตโนมัติ)</div>
          </div>
        </label>
```

with:

```html
        <label class="radio-card {{ 'sel' if s.extract_engine == 'llm' }}">
          <input type="radio" name="extract_engine" value="llm" {{ 'checked' if s.extract_engine == 'llm' }}>
          <div class="rc-body">
            <div class="rc-title">Gemini (LLM) <span class="rc-tag rec">แม่นยำกว่า</span></div>
            <div class="rc-desc">แม่นกว่าในรีวิวภาษาธรรมชาติ — ต้องตั้ง GEMINI_API_KEY (ขอฟรีที่ Google AI Studio; ถ้าไม่มีจะใช้ rule-based อัตโนมัติ)</div>
          </div>
        </label>
```

- [ ] **Step 3: `README.md` — rewrite §🤖 "เครื่องยนต์สกัดวลี"**

Replace the whole section body under `## 🤖 เครื่องยนต์สกัดวลี (Extraction engines)` (the two engine bullets, the "ตั้งค่า" block, and the "ค่าใช้จ่าย" block) with:

```markdown
ระบบเลือกได้ 2 เครื่องยนต์สำหรับ "การสกัดวลี" (ปรับได้จากหน้า **Settings**):

- **Rule-based (ค่าเริ่มต้น):** pipeline เชิงพจนานุกรมตามหัวข้อด้านบน — ทำงาน
  **ออฟไลน์ ไม่มีค่าใช้จ่าย และอธิบายผลลัพธ์ได้ทุกขั้นตอน**
- **Gemini (LLM) — เลือกใช้เพิ่มเติม (opt-in):** ส่งรีวิวให้ Google Gemini สกัดวลีความเห็น
  พร้อมหมวดและอารมณ์โดยตรง มักแม่นกว่าในรีวิวภาษาธรรมชาติที่หลากหลาย/ไม่เป็นทางการ

### ตั้งค่า

ตั้งค่าใน `.env`:

- `GEMINI_API_KEY` — **ต้องตั้งค่านี้** เพื่อเปิดใช้เครื่องยนต์ Gemini
  (ขอ key ฟรีที่ [Google AI Studio](https://aistudio.google.com))
- `GEMINI_MODEL` (ไม่บังคับ) — ค่าเริ่มต้น `gemini-2.5-flash`

และต้องติดตั้ง SDK: `pip install google-genai` (อยู่ใน `requirements.txt` แล้ว)

ถ้าไม่ได้ตั้ง `GEMINI_API_KEY` (หรือไม่ได้ติดตั้ง `google-genai` SDK) หรือเรียก API
แล้วเกิดข้อผิดพลาด ระบบจะ **fallback กลับไปใช้ rule-based โดยอัตโนมัติ** —
เลือก "Gemini (LLM)" ในหน้า Settings ไว้ได้โดยไม่ทำให้ระบบล่ม

### ค่าใช้จ่าย

Gemini มี **free tier** จาก Google AI Studio (มีลิมิตจำนวนคำขอต่อนาที/ต่อวัน) —
การวิเคราะห์หนึ่งครั้งส่งรีวิวทั้งชุดเป็น request เดียว จึงอยู่ในโควตาฟรีได้สบายสำหรับ
งานระดับโครงงาน
```

Also update the test count line — replace `**133 เทสต์**` with `**136 เทสต์**`.

- [ ] **Step 4: `scripts/compare_engines.py` — docstring + flag wording**

In the module docstring, replace `Claude (LLM)` with `Gemini (LLM)` and `ANTHROPIC_API_KEY` with `GEMINI_API_KEY`. In `main()`, change the `--llm` help text:

```python
    ap.add_argument("--llm", action="store_true", help="also run the Gemini engine")
```

- [ ] **Step 5: Run the full suite**

Run: `python -m unittest discover -s tests`
Expected: `OK` — **136 tests** (133 prior + 3 from `test_config_gemini.py`).

- [ ] **Step 6: Verify the README count matches reality**

Run: `python -m unittest discover -s tests 2>&1 | grep "Ran"`
Expected: `Ran 136 tests` — must equal the number written in README. Fix README if it drifts.

- [ ] **Step 7: Commit**

```bash
git add .env.example templates/settings.html README.md scripts/compare_engines.py
git commit -m "docs: Claude -> Gemini wording (.env, settings, README, compare)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Verify the real google-genai call shape

The mocked tests do not exercise the real SDK. Confirm the call signature before relying on it.

**Files:** none (verification only)

- [ ] **Step 1: Confirm the SDK call shape against the installed package / official docs**

Do NOT trust memory for the SDK signature. Confirm all of:
- `from google import genai` and `genai.Client(api_key=...)` exist.
- `client.models.generate_content(model=..., contents=<str>, config=<dict|GenerateContentConfig>)` exists.
- `config` accepts a **dict** with keys `system_instruction`, `response_mime_type`, `response_schema` (if the installed version requires `types.GenerateContentConfig`, switch `gen_config` to `from google.genai import types; types.GenerateContentConfig(**gen_config)` and re-run the mocked test).
- the response exposes the JSON string as `resp.text`.

Check via the installed package:
Run: `pip show google-genai` (note the version), then read the package's `generate_content` signature, or the official docs at `https://googleapis.github.io/python-genai/`.

- [ ] **Step 2: (Optional) Live smoke test if a key is available**

Only if `GEMINI_API_KEY` is set in the environment:

```bash
python -c "import os; os.environ.setdefault('GEMINI_API_KEY', os.environ.get('GEMINI_API_KEY','')); from core.phrases import llm_extract; print('available:', llm_extract.available()); print(llm_extract.extract_all([{'text': 'อาหารอร่อยมาก แต่บริการช้า รอนาน'}]))"
```
Expected: a contract dict with `service.negative` containing a wait-related phrase and `food.positive` containing a tasty-food phrase. If the call shape was wrong, fix `extract_all`/`gen_config` and re-run Task 2 Step 4.

- [ ] **Step 3: If any fix was needed, commit it**

```bash
git add core/phrases/llm_extract.py
git commit -m "fix(llm): align generate_content call with installed google-genai

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Done criteria

- `python -m unittest discover -s tests` → `OK`, 136 tests.
- `git grep -n "anthropic\|ANTHROPIC\|claude" -- "*.py"` → no matches.
- Settings page shows "Gemini (LLM)"; `.env.example`, README, and `compare_engines` reference `GEMINI_API_KEY`.
- With no key/SDK: app runs in demo + rule mode unchanged; selecting "Gemini (LLM)" falls back to rule silently.
