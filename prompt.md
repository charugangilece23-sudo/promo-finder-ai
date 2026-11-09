Here is a complete, copy-pasteable prompt you can give to another AI model to integrate a real LLM into this project.

---

# Prompt for Integrating a Real LLM into Promo Finder

## 1. Project Overview

This is **Promo Finder**, a Python application that reads TV microdrama screenplay transcripts and recommends 20–60 second promo clips. Each promo must open with a hook, end on an unresolved cliffhanger, and make sense to someone who has never seen the show.

The system is already fully implemented in **deterministic Python**. Your job is to connect a **real LLM provider** (Gemini, OpenAI-compatible, or Anthropic) so the LLM can judge story qualities that rules cannot (hook strength, cliffhanger strength, emotional intensity, narrative coherence, standalone understandability).

**Critical design rule:** The LLM never chooses or alters timestamps, durations, or cut points. All of that is deterministic code. The LLM only returns scores, verbatim quotes, and short text, referenced by candidate/event IDs.

---

## 2. Repository Structure (relevant files)

```
src/promo_finder/
├── cli.py                    # argparse entry point; calls pipeline.run()
├── pipeline.py               # stage orchestration (parse → timeline → generate → evaluate → score → dedupe → rank → write)
├── config.py                 # YAML + env var config loader (pydantic-validated)
├── models.py                 # pydantic models (Event, Episode, Candidate, Promo, ScoreBreakdown, etc.)
├── ingestion/
│   ├── loader.py             # loads .txt files, sorts by episode number
│   └── parsers/
│       └── kuku_screenplay.py  # parses the transcript format
├── preprocess/
│   ├── timeline.py           # builds Timeline (shots, beats, dialogue intervals)
│   └── normalizer.py         # text normalization
├── candidates/
│   ├── cutpoints.py          # legal cut points (never mid-dialogue)
│   ├── generator.py          # enumerates valid 20–60s windows
│   ├── features.py           # deterministic hook/cliffhanger/emotion/coherence/standalone/duration features
│   └── prefilter.py          # clusters overlapping windows, caps candidates per episode
├── llm/
│   ├── base.py               # LLMClient protocol + LLMResult dataclass
│   ├── factory.py            # build_client() from config/env (MOCK provider registered)
│   ├── prompts.py            # loads versioned prompt templates from config/prompts/
│   ├── schemas.py            # pydantic schemas (EvalOut, BlindOut, etc.)
│   ├── cache.py              # JSON file cache keyed by SHA-256
│   ├── retry.py              # exponential backoff + one JSON-repair retry
│   └── providers/
│       ├── mock.py           # MockLLM (deterministic, no API key) — replace/extend here
│       ├── gemini.py         # Gemini adapter skeleton (lazy import)
│       ├── openai_compat.py  # OpenAI-compatible adapter skeleton (lazy import)
│       └── anthropic.py      # Anthropic adapter skeleton (lazy import)
├── scoring/
│   ├── scorer.py             # score fusion: s_i = α·llm + (1−α)·det, weakest-link penalty
│   ├── evaluator.py          # calls LLM per batch, validates via grounding, fallback
│   ├── flags.py              # risk flags (LOW_HOOK, NO_LLM, etc.)
│   ├── dedupe.py             # overlap removal
│   └── ranker.py             # deterministic ranking
├── validation/
│   └── grounding.py          # validates LLM quotes/event IDs against source
└── reporting/
    ├── json_writer.py        # writes promos.json, episodes.json, run_manifest.json, candidates_debug.json
    └── markdown_report.py    # writes report.md
```

Config files:
- `config/default.yaml` — weights, llm_share, duration rules, cut rules, tiers, llm section
- `config/lexicons/en.yaml` — delivery-tag intensities, shock terms, cliffhanger terms
- `config/prompts/evaluate.md` — the per-candidate evaluation prompt (versioned)
- `config/prompts/blind.md` — the blind viewer standalone prompt

Tests live in `tests/`. Run with `pytest -q`.

---

## 3. What You Need to Do

### Step A: Pick and install one provider SDK

Add exactly one to `requirements.txt` and install it:

- **Gemini:** `pip install google-genai` (reads `GEMINI_API_KEY`)
- **OpenAI-compatible:** `pip install openai` (reads `OPENAI_API_KEY`, optional `OPENAI_BASE_URL` for OpenRouter/Groq/Ollama)
- **Anthropic:** `pip install anthropic` (reads `ANTHROPIC_API_KEY`)

SDKs are **lazy-imported** inside their adapter files, so the pipeline runs without them.

### Step B: Wire the provider into `llm/factory.py`

`build_client()` currently returns `MockLLM` by default. Add a branch for your provider:

```python
if provider == "gemini":
    from promo_finder.llm.providers.gemini import GeminiLLM
    return GeminiLLM(model=model)
```

Follow the pattern in `mock.py`, `gemini.py`, `openai_compat.py`, or `anthropic.py`. Each adapter must:
- Implement `LLMClient` protocol (from `llm/base.py`)
- Lazy-import its SDK inside the class/method (not at module top)
- Read its API key only from `os.environ` (never hard-coded)
- Implement `generate_json(system, prompt, schema, temperature, max_tokens) -> LLMResult`
- Use JSON/schema mode when available; otherwise instruct JSON-only and parse with pydantic
- Return `LLMResult(parsed=..., raw_text=..., usage=..., model=...)`

### Step C: Configure the model

Set environment variables (or edit `config/default.yaml`):

```
PROMO_LLM_PROVIDER=gemini
PROMO_LLM_MODEL=gemini-1.5-flash
PROMO_FINALIST_MODEL=gemini-1.5-pro
GEMINI_API_KEY=your-key
```

Then run:
```bash
python -m promo_finder run --input data/input
```

### Step D: Verify the integration

1. `pytest -q` must pass (102 tests, all mock-based, no network).
2. `python -m promo_finder run --input data/input` should complete without crashing.
3. Check `outputs/<run_id>/promos.json`:
   - `run.llm.mode` should be `"llm"` not `"heuristic_only"`
   - `run.llm.actual_model` should reflect your model
   - Promos should have non-null `hook`/`cliffhanger` blocks with real event IDs and quotes
4. Run the invariant checker:
   ```bash
   python eval/check_invariants.py
   ```
   Must report `Errors: 0`.

---

## 4. Hard Invariants (never violate these)

These are checked by `eval/check_invariants.py` and tests:

| Invariant | Meaning |
|-----------|---------|
| **I1** | LLM never produces, chooses, or alters timestamps. All times come from parsed source events. |
| **I2** | LLM refers to candidates/events only by ID. Unknown IDs are discarded. |
| **I3** | Every hook/cliffhanger quote must be a verbatim (normalized) substring of the referenced source event. Otherwise replaced by a code-chosen quote and flagged `UNGROUNDED_LLM_TEXT`. |
| **I4** | Every promo: 20–60s total; each segment `end > start`; within bounds; chronological, non-overlapping; boundaries at legal cut points; no cut strictly inside a dialogue interval. |
| **I6** | Pipeline must run with no API key (heuristic-only mode, flagged `NO_LLM`). |

---

## 5. How the LLM is Used (data flow)

1. **Prefilter** (`candidates/prefilter.py`) reduces thousands of windows to ≤18 per episode using deterministic features.
2. **Evaluator** (`scoring/evaluator.py`) batches ≤20 candidates per LLM call.
3. For each candidate, it builds a prompt with:
   - A compact transcript of the candidate's events (IDs, times, speakers, text)
   - The candidate's `cand_id`, `start_event_id`, `end_event_id`, `duration`
4. The LLM returns an `EvalOut` (pydantic-validated JSON) with:
   - `hook`, `cliffhanger`, `emotion`, `coherence`, `standalone` scores (1–5)
   - `hook_detail` / `cliffhanger_detail` with `event_id`, `quote`, `description`
   - `why_it_works`, `weaknesses`, `reject`, `reject_reason`
5. **Grounding** (`validation/grounding.py`) checks:
   - `cand_id` matches the candidate
   - `hook.event_id` and `cliffhanger.event_id` are inside the candidate's event range
   - Hook event is within first 3s; cliffhanger within last 5s
   - Quotes are normalized substrings of the source event text
6. On any validation failure after one repair retry, the candidate falls back to heuristic scoring with `LLM_INVALID` flag.
7. **Scorer** (`scoring/scorer.py`) fuses: `s_i = α·llm_i + (1−α)·det_i`, then applies weakest-link penalty.

---

## 7. Prompt Templates

The prompts live in `config/prompts/` with a `version:` header. Key requirements:
- `evaluate.md`: sends compact transcript once per episode; candidates referenced by ID; anchored 1–5 rubric; explicit rule "No timestamps, quote verbatim, refer by ID only"
- `blind.md`: receives **only** the clip's events (no loglines, no profile, no other episodes)
- Changing a prompt bumps its version so cached results are not reused incorrectly

---

## 8. Testing

- **No network in tests.** All LLM behavior in tests goes through `MockLLM`.
- Add tests in `tests/` for any new provider adapter using `MockLLM`.
- Run `pytest -q` after changes.
- If you test with a real API key, explain cost/quota first and show 2–3 raw trace files from `outputs/<run_id>/llm_trace/`.

---

## 9. Things You Must NOT Do

- Do not hard-code API keys. Read from environment variables only.
- Do not let the LLM output or choose timestamps. If a model emits times, ignore them.
- Do not ask the LLM for a final rank or score. It only provides dimension ratings (1–5).
- Do not hard-code episode numbers, character names, or filenames in `src/`.
- Do not add LangChain, databases, queues, or web servers.
- Do not commit `.env`, `data/input/`, or `outputs/`.

---

## 10. Example: Running with Gemini

```bash
# Install SDK
pip install google-genai

# Set env (PowerShell)
$env:PROMO_LLM_PROVIDER="gemini"
$env:PROMO_LLM_MODEL="gemini-1.5-flash"
$env:GEMINI_API_KEY="your-key"

# Run
python -m promo_finder run --input data/input
```

Or override on CLI:
```bash
python -m promo_finder run --input data/input --provider openai --model gpt-4o-mini
```

---

If anything is unclear, look at `llm/providers/mock.py` first — it is the simplest complete example of the `LLMClient` protocol. The `scoring/evaluator.py` file shows exactly how the pipeline calls the client and handles failures.