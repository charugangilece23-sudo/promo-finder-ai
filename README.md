# Promo Finder — Kuku AI Generalist Assignment, Problem 1

**Find the Promos:** an AI-powered promo discovery system for TV microdrama
screenplay transcripts. It reads `.txt` screenplay files, recommends the best
20–60 s promo clips (each with a hook, cliffhanger, verbatim quotes, and a
transparent quality score), and exports ranked results to JSON and Markdown.

---

## What the project does

Given a directory of screenplay transcripts (one per episode), the tool:

1. **Parses** each transcript into structured events (shots, actions, dialogue)
   with episode-relative timestamps.
2. **Builds a timeline** and computes *legal cut points* (never mid-dialogue).
3. **Generates every valid candidate window** (20–60 s, boundaries at legal cut
   points).
4. **Scores** each candidate with deterministic features (hook, cliffhanger,
   emotion, coherence, standalone, duration) plus optional LLM judgement.
5. **Deduplicates** overlapping windows and **ranks** them by a fused score with
   a weakest-link penalty (a great cliffhanger but no hook is downgraded).
6. **Exports** `promos.json`, `report.md`, `episodes.json`,
   `candidates_debug.json`, and `run_manifest.json` to `outputs/<run_id>/`.

Every output timestamp equals an actual event boundary in the source — the LLM
never chooses or alters timestamps (invariant I1).

---

## How the system works

| Stage | What it does | LLM? |
|-------|--------------|------|
| Ingestion | Parse `.txt` → episodes, scenes, events (IDs `E{ep:03d}:{idx:03d}`) | No |
| Timeline | Shots vs beats; dialogue intervals; legal cut points | No |
| Generate | Enumerate all (start, end) windows, 20–60 s, dialogue-safe cuts | No |
| Features | Deterministic hook/cliffhanger/emotion/coherence/standalone/duration | No |
| Prefilter | Score + cluster overlapping windows; keep top variants per cluster | No |
| Evaluate | LLM rates hook/cliffhanger/emotion/coherence/standalone by event ID | Yes |
| Grounding | Validate LLM quotes/event IDs against source; neutralise hallucinations | No |
| Score | Fuse det + LLM (`α·llm + (1−α)·det`), weakest-link penalty | No |
| Dedupe + Rank | Overlap removal; sort by score with deterministic tie-breaks | No |
| Output | `promos.json`, `report.md`, manifest, debug dump | No |

**Deterministic code owns:** parsing, timestamps, cut points, durations,
validation, score fusion, dedupe, ranking.
**The LLM owns only:** story judgement (hook/cliffhanger/emotion/coherence/
standalone ratings and text), referenced by candidate/event IDs.

The pipeline runs end-to-end **with no API key** in heuristic-only mode
(flagged `NO_LLM`), and with a real LLM when credentials are provided.

---

## Technologies used

- **Python 3.11+**
- **pydantic v2** — data models and LLM-output validation
- **PyYAML** — config and lexicons
- **python-dotenv** — environment variables
- **pytest** — testing
- Provider SDKs (lazy-imported, optional): `google-genai`, `openai`, `anthropic`

No vector DB, agent framework, queue, database, or web server. The CLI and
Markdown report are the interfaces (an optional Streamlit UI is Phase 9 and not
built).

---

## Installation

```bash
# Clone / open the project folder
cd promo_finder_AI

# Create a virtual environment (a private folder of Python packages for this
# project so it doesn't clash with other projects)
python -m venv .venv

# Activate it
#   macOS/Linux:
source .venv/bin/activate
#   Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# (Editable install so `python -m promo_finder` works)
pip install -e .
```

Transcripts are expected in `data/input/` (git-ignored, confidential). Copy
your screenplay `.txt` files there.

---

## Environment configuration

Copy `.env.example` to `.env` and fill in the provider you want to use:

```bash
cp .env.example .env
# edit .env with your API key(s)
```

Relevant variables (names only, no secrets committed):

| Variable | Purpose |
|----------|---------|
| `PROMO_LLM_PROVIDER` | `mock` | `gemini` | `openai` | `anthropic` |
| `PROMO_LLM_MODEL` | eval model (cheap, high volume) |
| `PROMO_FINALIST_MODEL` | stronger model for finalists (optional) |
| `GEMINI_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | API keys, env only |
| `OPENAI_BASE_URL` | OpenAI-compatible endpoint (OpenRouter, Groq, Ollama, …) |

API keys are read only from environment variables — never hard-coded, never
logged.

---

## How to run the application

```bash
# Heuristic-only mode (no API key needed)
python -m promo_finder run --input data/input --no-llm

# With LLM (provider from .env)
python -m promo_finder run --input data/input

# Inspect parsed transcripts (debug table)
python -m promo_finder inspect --input data/input

# Run tests
pytest -q
```

Outputs go to `outputs/<run_id>/` (a UTC-timestamped folder, never overwrites
a previous run): `promos.json`, `report.md`, `episodes.json`,
`candidates_debug.json`, `run_manifest.json`.

---

## How to process new screenplay transcripts

Place `.txt` screenplay files in any input directory (one file per episode,
the Kuku format described below) and run:

```bash
python -m promo_finder run --input /path/to/transcripts --no-llm
```

The parser is format-agnostic via a registry: new transcript formats are
supported by adding a new parser class, not by rewriting existing code. No
episode numbers, character names, or plot facts are hard-coded, so the tool
generalises to new shows without code changes (NFR-08).

---

## How to interpret the results

- `report.md` — ranked table and per-promo cards (hook, cliffhanger, why it
  works, score breakdown, weaknesses/risks).
- `promos.json` — machine-readable, one entry per promo with `promo_id`,
  `rank`, `tier` (A/B/C), `score`, `score_breakdown`, `segments` (each with
  start/end as `MM:SS.ss` and float seconds, plus `start_event_id` /
  `end_event_id` and transcript excerpt), `hook`, `cliffhanger`, `flags`.
- `run_manifest.json` — config, models, prompt versions, per-stage timings.
- `candidates_debug.json` — all scored candidates including rejected ones.
- Flags like `LOW_HOOK`, `WEAK_CLIFFHANGER`, `NEEDS_CONTEXT`, `NO_LLM` tell you
  where a recommendation may be wrong.

---

## Known limitations

- **Text-only input:** the tool sees screenplay text and timestamps, not video,
  so purely visual hooks/cliffhangers may be under-scored.
- **Heuristic-only mode** (no API key): scores are rule-based; tier capped at B.
- **Speaker aliases:** the same character may appear under different labels
  (e.g. `MATRIARCH` / `NOBLE MATRIARCH`); descriptions may treat them as
  distinct unless a per-show `shows/<slug>/profile.yaml` alias map is edited.
- **Resolved endings:** an episode ending is a soft cliffhanger prior, not
  automatic — a resolved finale may be over-scored.
- **No diversity pass:** several top promos may come from the same scene (MVP
  removes overlaps but has no cross-arc diversity).
- **Untuned weights:** scoring weights are starting values, not fitted to
  editor feedback.
- **Only 3 of 50 episodes** were available when the design was written; this
  build actually has all 50 locally, but behaviour on the full pack and on
  other shows is unproven until run.
- Stitching (multi-segment promos ≤ 2 segments) is deferred (Phase 4b) — the
  MVP produces contiguous single-segment promos, which is a valid deliverable.

See `AGENTS.md` §15 Decision Log and `architecture.md` §14 for the full
evaluation strategy and expected failure modes.

---

## Repository structure

```
promo_finder_AI/
├── README.md
├── architecture.md          # technical design
├── AGENTS.md                # development process + progress tracker
├── requirements.txt         # core dependencies
├── requirements-ui.txt      # optional Streamlit UI (Phase 9, not built)
├── .env.example             # env var names (no secrets)
├── .gitignore
├── pyproject.toml
├── config/
│   ├── default.yaml         # durations, cut rules, weights, α, tiers
│   ├── lexicons/en.yaml     # shock/reveal terms, delivery-tag intensities
│   └── prompts/             # versioned LLM prompts (profile, evaluate, blind)
├── data/input/              # screenplay .txt files (git-ignored, confidential)
├── src/promo_finder/        # application code
├── tests/                   # automated tests
├── eval/check_invariants.py # I1–I4 invariant checker
└── outputs/                 # run results (git-ignored)
```

Run `pytest -q` to execute the test suite (102 tests, all pass on this build).

---

*Raw output files quote confidential screenplay text — share privately or by
restricted link; do not commit or publish them.*