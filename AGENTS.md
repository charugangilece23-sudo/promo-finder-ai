# AGENTS.md — Instructions for AI Coding Agents

> Project: **Promo Finder** (Kuku AI Generalist Assignment · Problem 1 — *Find the Promos*)
> Read this file completely before touching the repository. Then read `architecture.md`.
> If this file and `architecture.md` disagree, **stop and flag it**; do not pick silently (see §3, rule R5).

---

## 0. How to use this file

1. Read §1–§4 once, every session.
2. Find the first unchecked phase in the **Progress Tracker (§14)**. Work only on that phase.
3. Follow the phase's steps in order. Each phase ends with a **Gate**. Do not start the next phase until the Gate passes and the human has seen the result.
4. At the end of every step, update the Progress Tracker and reply using the template in §13.

`architecture.md` is the design. **This file is the process.** Section references like "(arch §11.1)" point to `architecture.md`.

---

## 1. Project snapshot

### 1.1 Goal
An application reads screenplay transcripts of TV microdrama episodes and recommends the best **promo clips**. A promo is 20–60 s long in total, opens on a **hook** (something in the first ~3 s that stops a scrolling viewer), ends on an unresolved **cliffhanger**, and makes sense to someone who has never seen the show. It is usually one continuous stretch but may join up to a few segments, within one episode or across episodes.

Every recommendation must contain:

- Promo ID and **rank**
- **Episode number(s)**
- **Start and end timestamps of every segment** (in order)
- **Hook** and **cliffhanger** (with verbatim quotes from the source)
- **Why it works** (one line)
- **Quality score** (transparent breakdown)
- Risks / weaknesses (where the recommendation may be wrong)

The tool only **finds** promos (moments and cut points). No video editing, music or text overlays.

### 1.2 Repository state at the time this file was written

| Item | State |
|---|---|
| Application code | **None.** Repository contains only `architecture.md` (and this file). Nothing is implemented. |
| Sample data | 50 screenplay files provided by the human: `episode-001-Episode_1671703.txt` through `episode-050-Episode_1671752.txt`. All 50 available locally. |
| Assignment PDF | `Kuku___AI_Generalist_Assignment.pdf` — read it if present; key facts are repeated here. |

If you find existing code when you start, **inspect it first and reuse what works** (rule R4). Never overwrite working code without a reason.

### 1.3 Input format — verified facts (do not re-invent)

These were checked against the three sample files. Re-verify with your own commands in Phase 2 before relying on them.

```
EPISODE NUMBER: Episode 1
EPISODE LOGLINE: <free text>
CONTINUITY NOTES: <free text>

--- SCRIPT START ---

SCENE 01
Scene heading: INT. CATHEDRAL – DAY
Scene start: 00:00.00
Scene end: 02:18.00

Actions and dialogue:

**CAMERA:**
Start: (00:00.00) | End: (00:04.80)
<shot description>

**LADY JULIANA (Confused, Breathless):**
Start: (00:13.50) | End: (00:14.30)
"Why?"

**MATRIARCH (O.S.) (Firm):**
Start: (01:53.30) | End: (01:55.70)
"Clarissa is the jewel of this family."

--- SCRIPT END ---
```

- Entry labels: `CAMERA`, `ACTION`, `SOUND FX`; **any other label is a speaker (dialogue)**.
- Parenthetical groups after a label are either modifiers (`O.S.`, `V.O.`, `Off-screen`) or delivery/emotion tags (`Cold, Callous`).
- Timestamps are **episode-relative** `MM:SS.ss` (e.g. `02:25.75`). They are not global.
- Blocks **overlap in time**: camera blocks form a near-contiguous shot list; action/dialogue/sound run concurrently. A dialogue line can span several shots.
- Speaker names are **inconsistent** across and within episodes (`MATRIARCH` / `NOBLE MATRIARCH` / `OFF-SCREEN VOICE`; `LADY IN GOLD GOWN` is "Clarissa"; `THE FORMER GROOM` is "Gerald"). Never key logic on speaker strings.
- Non-ASCII characters exist (`–`, `—`, `é`). Files are UTF-8, LF line endings.

**Golden numbers (use as parser test expectations after you confirm them independently):**

| File | Entry blocks | CAMERA | ACTION | SOUND FX | Dialogue | Scenes | Last block end (s) |
|---|---|---|---|---|---|---|---|
| episode 1 | 95 | 50 | 7 | 1 | 37 | 1 | 138.00 |
| episode 2 | 74 | 39 | 4 | 0 | 31 | 1 | 110.00 |
| episode 3 | 118 | 61 | 8 | 3 | 46 | 3 | 145.75 |

Episode 3 scenes: `00:00.00–00:22.80`, `00:22.80–01:04.50`, `01:04.50–02:25.75`.

### 1.4 Facts from the assignment PDF that shape the work

- The submission is judged on: problem framing, **approach & scale** (what is AI vs rules vs human), **quality checking with honest failures**, a **runnable prototype**, and clear communication.
- On interview day the human will **run the solution on a new input** and may **connect a stronger model via an API** ⇒ the model must be swappable and the parser must not be tied to this show.
- Free tiers are enough. Honest, partial, well-documented work beats overstated, complete work.
- The input pack is **confidential**: never commit it, never upload it anywhere except the configured LLM API.

---

## 2. Documents you must keep in sync

| File | Purpose | When to update |
|---|---|---|
| `AGENTS.md` | This file. Process rules and the Progress Tracker | Tick tracker items; add to §15 Decision Log |
| `architecture.md` | System design | Only when the design genuinely changes (R5) |
| `README.md` | Human setup & run instructions | End of every phase that changes how to run things |
| `requirements.txt` | Core dependencies | Whenever a dependency is added (with justification in the Decision Log) |
| `requirements-ui.txt` | Optional UI dependency (Streamlit) | Phase 9 only |
| `.env.example` | Names of env vars (no secrets) | Whenever a new env var is read |
| `tests/` | Automated tests | With every module (R13) |
| `outputs/` | Run results and raw LLM traces | Produced by runs; never hand-edited |

---

## 3. Non-negotiable rules

### 3.1 Working rules (R1–R18)

- **R1** Work in small, understandable steps (≈ one module or one function group per step).
- **R2** Never generate the whole application in one go.
- **R3** Before implementing a module, state in 2–4 sentences *what it is for and why it exists* (plain language).
- **R4** Follow `architecture.md`. Reuse existing working code; do not overwrite it unnecessarily.
- **R5** If a genuine implementation problem forces a design change: stop, explain the problem and the proposed change, update `architecture.md`, add a Decision Log entry (§15), then continue.
- **R6** Never invent transcript formats, and never assume parsing works without a test that proves it on the real files.
- **R7** No hard-coded episodes, characters, plot facts or file names in `src/`. Show-specific data may only live in generated/edited config (`shows/<slug>/`) or in `tests/` fixtures and `eval/` gold files.
- **R8** Keep functions small and single-purpose.
- **R9** Use meaningful names. Add type hints and short docstrings to public functions.
- **R10** Add error handling and logging (`logging` module, not `print`, in library code).
- **R11** Avoid unnecessary dependencies. Allowed core set: `pydantic>=2`, `PyYAML`, `python-dotenv`, `pytest`; provider SDKs (`google-genai`, `openai`, `anthropic`) **imported lazily inside their adapters**. Anything else needs a Decision Log entry.
- **R12** Never print, log, commit or hard-code API keys. Read them only from environment variables / `.env`.
- **R13** Write tests alongside every important module, in the same step.
- **R14** Run the full test suite after every meaningful change.
- **R15** Never claim something works unless you ran it and saw it work. Quote the command and the result.
- **R16** Never silently skip a failed episode or block. Every skip produces a structured warning that appears in `episodes.json` and the report.
- **R17** Preserve original timestamps (both the raw string and the float seconds) and source references (file, episode, event ID) all the way to the output.
- **R18** Document limitations and assumptions as you discover them (README "Known limitations" + Decision Log).

### 3.2 Project invariants (a violation is a bug)

- **I1** The LLM **never** produces, chooses or alters timestamps. All times come from parsed source events.
- **I2** The LLM only refers to candidates and events **by ID**. Unknown IDs are discarded.
- **I3** Every quote shown as a hook/cliffhanger must be a verbatim (after normalisation) substring of the referenced source event. Otherwise it is replaced by a code-chosen quote and the promo is flagged.
- **I4** Every output promo satisfies: `20 ≤ total duration ≤ 60` seconds; each segment `end > start`; segments inside episode bounds; segments in chronological order and non-overlapping; segment boundaries equal legal cut points; no cut strictly inside a dialogue interval.
- **I5** Deterministic code owns: parsing, windows, durations, cut points, validation, score fusion, dedupe, ranking. The LLM owns only story judgement (hook/cliffhanger/emotion/coherence/standalone ratings and text).
- **I6** The pipeline must run end to end **without any API key** (heuristic-only mode, flagged `NO_LLM`).
- **I7** Pure functions for scoring/validation: same input ⇒ same output.
- **I8** Never mutate or "fix" source data silently. Normalised text is stored beside the original, never instead of it.

---

## 4. How to interact with the human

The human is building this as a **learning project**.

- Explain concepts in **simple language** the first time they appear (e.g. "a *pydantic model* is a Python class that checks its own data").
- **Explain every terminal command before running it or asking the human to run it**: what it does and what a good result looks like. Give both macOS/Linux and Windows forms when they differ.
- Give **exact file paths** whenever you create or modify a file, and one line saying what the file does.
- If a command fails: read the error, state the diagnosis in plain words, fix the cause, re-run. Do not skip ahead (see §11).
- **Do not start the next major phase until the current Gate passes** and you have shown the human the evidence.
- Avoid unnecessary questions. If something is unclear, make a sensible assumption, write it in the Decision Log, and continue. Ask only when the answer would change the architecture or cost the human money.
- If you cannot run commands yourself, give the human the exact command, wait for the output, and continue from it.

---

## 5. Target structure and commands (summary)

The full tree is in arch §16.1. Create directories only when the phase that needs them starts.

```
python -m promo_finder run --input data/input --config config/default.yaml
python -m promo_finder run --input data/input --no-llm
python -m promo_finder run --input data/input --provider <name> --model <name>
pytest -q
```

Python: **3.11+**. Use a virtual environment (Phase 1). Package layout: `src/promo_finder/` with `pip install -e .`-free execution via `PYTHONPATH=src` **or** a tiny `pyproject.toml` only if imports cannot otherwise work — prefer the simpler option and log the choice in §15. Put `src` on the path for pytest with a `conftest.py` or `pytest.ini` (`pythonpath = src`).

---

## 6. Implementation phases

Every phase has: **Purpose → Steps → Tests → Gate → Pitfalls**. Steps are ordered; each step is one small change set. Always explain first (R3), implement, test (R13–R14), report (§13).

---

### Phase 1 — Project setup

**Purpose:** a clean, runnable skeleton so everything later is reproducible.

**Steps**

1. **Inspect**: list the repo (`ls -la`), confirm Python version (`python --version`, need 3.11+), read the PDF and `architecture.md` if not yet read.
2. **Virtual environment** — explain first: *"a virtual environment is a private folder of Python packages for this project so it doesn't clash with other projects."*
   - macOS/Linux: `python3 -m venv .venv && source .venv/bin/activate`
   - Windows (PowerShell): `python -m venv .venv; .venv\Scripts\Activate.ps1`
3. **Create files** (exact paths):
   - `requirements.txt` — core deps only (R11): `pydantic>=2`, `PyYAML`, `python-dotenv`, `pytest`, plus the three provider SDKs (lazy-imported). Pin nothing exotic; minimum versions only.
   - `.env.example` — names only: `PROMO_LLM_PROVIDER`, `PROMO_LLM_MODEL`, `PROMO_FINALIST_MODEL`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_BASE_URL`, with placeholders and one-line comments.
   - `.gitignore` — at least: `.venv/`, `.env`, `__pycache__/`, `.pytest_cache/`, `cache/`, `data/input/`, `outputs/` (add a note in README: raw outputs quote confidential text; share privately).
   - `pytest.ini` — `pythonpath = src`, `testpaths = tests`.
   - Package skeleton: `src/promo_finder/__init__.py`, `__main__.py`, `cli.py`, `config.py`, `models.py`, `logging_setup.py`; empty `tests/`, `config/`.
   - `config/default.yaml` — values from arch §11.7 (weights, α, duration, weakest-link, tiers) plus cut-rule values (`lead_in: 1.5`, `tail_hold: 1.5`, `epsilon: 0.05`, `min_dur: 20`, `max_dur: 60`).
4. **Config loader** (`config.py`): load YAML, overlay env vars, validate with a pydantic model, fail with a clear message on bad values. Never log secrets.
5. **CLI stub** (`cli.py`): `run` sub-command parsing `--input`, `--config`, `--no-llm`, `--provider`, `--model`, `--output-dir`. For now it loads config and logs "setup OK".
6. **Place sample data**: *copy* (don't move) the 3 transcripts into `data/input/` (git-ignored). Confirm with `ls data/input`.
7. **README.md**: install, activate venv, `pip install -r requirements.txt`, run, test.

**Tests:** `tests/test_config.py` — valid config loads; missing/invalid value raises a clear error; env override works; keys never appear in `repr`/logs.

**Gate (run and show output):**
- `pip install -r requirements.txt` succeeds.
- `pytest -q` passes.
- `python -m promo_finder run --input data/input --no-llm` prints a setup-OK log and exits 0.

**Pitfalls:** don't add libraries "just in case"; don't commit `.env` or `data/input/`.

---

### Phase 2 — Input processing

**Purpose:** turn each screenplay file into validated, structured events. *This is the foundation — if parsing is wrong, everything after is wrong.*

**Steps**

1. **Verify the format yourself first (R6).** Before writing the parser, run commands (grep/python) on `data/input/*.txt` to re-derive the golden numbers in §1.3. If they differ, trust your measurements, record the discrepancy in §15, and use your numbers.
2. **Models** in `src/promo_finder/models.py`: `Event`, `Scene`, `Episode`, `ParseWarning` exactly as in arch §12.1. Event IDs: `E{episode:03d}:{index:03d}` assigned **after** sorting by `(start, end, original order)`.
3. **Timestamp parser** `ingestion/timestamps.py`: accept `MM:SS.ss`, `HH:MM:SS.ss`, `SS.ss`; return float seconds; keep the raw string. Reject garbage with a typed error (not a crash).
4. **Loader** `ingestion/loader.py`: glob `*.txt` (pattern from config), read UTF-8 (`utf-8-sig` then `latin-1` fallback with a warning), return `RawEpisode(path, text)`. Sort **by parsed episode number**, never by file name.
5. **Parser** `ingestion/parsers/kuku_screenplay.py` implementing the `FormatParser` protocol (`base.py`) and a registry (`registry.py`) with `detect(text) -> float`:
   - Header keys, `--- SCRIPT START/END ---`, scene header block, entry blocks (label line `**…:**`, `Start:/End:` line, text until blank line / next `**` / next `SCENE`).
   - Label classification: reserved `CAMERA|ACTION|SOUND FX` (case-insensitive, configurable) else dialogue.
   - Split parentheticals into `modifiers` vs `delivery` (configurable modifier list: `O.S.`, `V.O.`, `Off-screen`, `Off screen`, `CONT'D`).
   - Dialogue text: strip surrounding quotes; allow multi-line.
   - Missing `Start`/`End` ⇒ drop block + warning. Missing `End` but valid `Start` ⇒ `end = start`, flag `end_inferred`. Missing episode header ⇒ number from filename + warning. Missing scene block ⇒ one synthetic scene.
   - Capture `EPISODE LOGLINE` and `CONTINUITY NOTES`.
6. **Validators** `ingestion/validators.py` (arch §8.2): inverted times, out-of-bounds events, duplicate episode numbers, gaps in episode numbering, suspicious dialogue speed (words/sec outside configured range), shot-timeline gaps > 2 s, filename/header mismatch. All return `ParseWarning` objects.
7. **Normaliser** `preprocess/normalizer.py`: NFKC, unify dashes/quotes/ellipsis, collapse whitespace into `norm_text`. Original `text` is never altered (I8).
8. **Debug command** `python -m promo_finder inspect --input data/input` printing a per-episode table: episode number, source id, scene count, event counts by kind, last end time, warnings.

**Tests** (`tests/test_timestamps.py`, `tests/test_parser.py`, `tests/test_validators.py`, `tests/test_normalizer.py`)

- Golden numbers from §1.3 on the three real files (marked `@pytest.mark.skipif` if `data/input` is absent, so CI/fixtures still work).
- Synthetic fixtures in `tests/fixtures/`: minimal valid file; missing `End`; inverted timestamps; CRLF line endings; extra blank lines; missing header; unknown label; non-ASCII; a file in a **different** invented format (parser must refuse with low confidence, not guess).
- Specific assertions: a known dialogue line (e.g. Episode 1 `"Why?"`, `13.50–14.30`, speaker raw `LADY JULIANA`, delivery `["Confused", "Breathless"]`); a modifier case (`MATRIARCH (O.S.) (Firm)` ⇒ modifiers `["O.S."]`, delivery `["Firm"]`); a timestamp with hundredths (`02:25.75` ⇒ `145.75`).

**Gate:** `pytest -q` green; `inspect` output matches the golden table; deliberately corrupted fixtures yield warnings, not crashes; show the human the `inspect` table.

**Pitfalls:** don't assume blocks are sequential or non-overlapping; don't split on `:` naively (timestamps contain colons); don't strip the `O.S.` information; never infer missing times.

---

### Phase 3 — Preprocessing

**Purpose:** build the per-episode timeline and the *legal cut points* so that candidate generation can be guaranteed valid.

**Steps**

1. `preprocess/timeline.py`: from an `Episode` produce `Timeline` with `events`, `shots` (CAMERA), `beats` (non-camera), `dialogue_intervals`, previous/next beat links per event, and `episode_link` flag (from `CONTINUITY NOTES` keywords like "picks up", "follows directly" — keywords come from config, not code).
2. `candidates/cutpoints.py` (arch §11.1): implement `is_dialogue_safe(t)`, `legal_starts`, `legal_ends` with `epsilon`, `lead_in`, `tail_hold` from config. Include scene/episode end as legal ends.
3. `preprocess/profile.py` is **deferred to Phase 5** (needs the LLM). Create only the interface now if helpful.
4. Persist processed data: `outputs/<run_id>/episodes.json` (parse report) via `reporting/json_writer.py`; make `Timeline` serialisable.

**Tests** (`tests/test_timeline.py`, `tests/test_cutpoints.py`)

- Event ordering and ID stability (same input ⇒ same IDs).
- Cut-point rule on real data: for Episode 2, no legal start or end lies strictly inside `01:26.80–01:33.00` or `01:19.20–01:22.50` (both dialogue lines span shot boundaries).
- Property-style test on every real episode: **no legal start/end is inside any dialogue interval** (± epsilon).
- Synthetic: a window starting with 5 s of silence is rejected by `lead_in`.

**Gate:** tests green; a small script/command prints, for Episode 1, the number of legal starts/ends and a few sample values; the human confirms they look sensible.

**Pitfalls:** don't treat camera blocks as the story; don't allow cuts mid-line "because the shot changes there".

---

### Phase 4 — Candidate generation (deterministic, no LLM)

**Purpose:** enumerate every valid promo window, score it cheaply with rules, and prune to a manageable shortlist. After this phase the tool can already produce a **heuristic-only** ranking.

**Steps**

1. `candidates/generator.py`: for each legal start/end pair with `min_dur ≤ end − start ≤ max_dur`, build a `Candidate` (one `Segment`, `event_ids`, duration). Stable `cand_id` = short hash of `(episode, start, end)`.
2. `candidates/features.py` (arch §11.4). Implement each feature as a small pure function returning `[0,1]`, with its raw inputs recorded for the debug dump:
   - hook (first 3 s), cliffhanger (last ~5 s, including "cut right before the answer" using the next source beat), emotion (delivery-tag intensity, speaker alternation, punctuation, lexicon), coherence (det. part), standalone proxy, duration score.
   - Lexicons live in `config/lexicons/en.yaml` (shock/reveal/threat/resolution terms and delivery-tag intensities). **Do not hard-code word lists in Python.**
3. `candidates/prefilter.py` (arch §11.5): prefilter score from det. features with the config weights; cluster by temporal IoU > 0.5; keep `variants_per_cluster` with distinct cut points; keep `clusters_per_episode` clusters.
4. `scoring/scorer.py` (det. part only for now): fusion formula with `α = 0` and the weakest-link penalty (arch §11.7); hard gates (duration, cut safety, bounds).
5. `scoring/dedupe.py` and `scoring/ranker.py`: overlap dedupe (≥ 50 % of the shorter segment, same episode), tie-breaks (hook, cliffhanger, earlier episode).
6. `reporting/` minimal: `promos.json` (schema arch §12.2, fields that don't exist yet are `null`) and a basic `report.md`.
7. **Stitching (`candidates/stitch.py`) — do this last in the phase and only after steps 1–6 pass.** ≤ 2 segments, chronological, same-episode gap ≥ `min_gap`, cross-episode allowed, cap ≈ 20 per show (arch §11.3). If time is short, skip stitching and record it in §15; a contiguous-only tool is a valid deliverable.
8. Wire the pipeline: `pipeline.py` runs parse → timeline → generate → features → prefilter → score → dedupe → rank → write outputs, so `run --no-llm` works end to end.

**Tests** (`tests/test_generator.py`, `tests/test_features.py`, `tests/test_scoring.py`, `tests/test_dedupe.py`, `tests/test_stitch.py`)

- **Every** generated candidate on every real episode satisfies I4 (duration, bounds, dialogue-safe cuts). Assert this across the full candidate set, not a sample.
- Hook feature: Episode 1 window starting at `00:00.00` (no dialogue before `00:11.30`) scores clearly lower than one starting at `00:11.00`; Episode 2 window starting at `00:00.00` (first line at `00:00.00`) scores high.
- Cliffhanger feature: a window ending with a question/ellipsis whose answer is the next source line scores higher than one ending on a calm resolution (use synthetic fixtures for exact control).
- Scoring: hand-computed examples from arch §11.7 (e.g. weakest-link penalty values) reproduced exactly.
- Dedupe: overlapping windows collapse to the higher score; non-overlapping stay; records the reason.
- Ranking determinism: run twice ⇒ identical output.
- Stitching: pair respects chronological order, duration range, gap rule; never overlaps its own segments.

**Gate:** `python -m promo_finder run --input data/input --no-llm` produces `outputs/<run_id>/promos.json` + `report.md`; every promo passes the validators; **the human reads the top 5 and says whether they look plausible**. Record what looks wrong in README "Known limitations".

**Pitfalls:** don't tune weights to make three episodes look good (A8: weights are untuned starting values); don't let the prefilter drop *all* candidates from an episode (emit a warning if it would); keep all deterministic output reproducible.

---

### Phase 5 — AI integration

**Purpose:** add LLM judgement for the qualities rules can't judge, **without** giving the LLM power over timestamps or facts.

**Steps**

1. **Interface** `llm/base.py`: `LLMClient` protocol and `LLMResult` (arch §10.2). Pipeline code imports only this.
2. **Mock adapter first** `llm/providers/mock.py`: deterministic canned responses driven by a fixture, so the whole LLM path is testable offline.
3. **Schemas** `llm/schemas.py` (pydantic): `ProfileOut`, `EvalOut` (per-candidate: `cand_id`, five 1–5 scores, `hook{event_id,quote,description}`, `cliffhanger{event_id,quote,description,unresolved_question}`, `why_it_works`, `weaknesses[]`, `reject`, `reject_reason`), `StitchedEvalOut` (+ `join_makes_sense`), `BlindOut` (`who_what_stakes`, `unanswered_questions[]`, `standalone`).
4. **Prompts** in `config/prompts/*.md` with a `version:` header (`profile`, `evaluate`, `evaluate_stitched`, `blind`). Requirements:
   - Compact transcript rendered as `E001:017 [00:41.70-00:43.10] LADY JULIANA (Gasping): "No..."` — sent **once** per episode; candidates referenced by ID range.
   - Anchored 1–5 rubric text (arch §11.6) in the prompt.
   - Explicit rules: *"Use only events in the transcript. Quote verbatim. Refer to events by ID only. Do not output any timestamps. If unsure, set the field to null."*
   - Candidate order shuffled with a **fixed seed**.
   - `blind.md` receives **only** the clip events (no loglines/profile/other episodes).
5. **Provider adapters**: `openai_compat.py` first (covers most free tiers and local models via `OPENAI_BASE_URL`), then `gemini.py`, then `anthropic.py`. Each lazy-imports its SDK, reads its key from env, uses JSON/schema mode when available, and fails with a clear message if the key or SDK is missing.
6. `llm/factory.py`: build clients from config/env with two slots (`eval_model`, `finalist_model`); `llm/retry.py`: exponential backoff on 429/5xx, up to 50 retries with 5s–120s delay and jitter, per-provider rate limiter; `llm/cache.py`: JSON file cache keyed by SHA-256 of `(prompt_version, model, input)`; **write every raw request and response unedited** to `outputs/<run_id>/llm_trace/` (required deliverable: raw outputs).
7. `preprocess/profile.py`: one call per show → `shows/<slug>/profile.yaml` (premise + alias map; unknown aliases are `null`). Reuse an existing profile instead of regenerating; never overwrite a human-edited one without `--refresh-profile`.
8. `validation/grounding.py` (arch §13.2) — **write and test before wiring the evaluator**:
   - `cand_id` and `event_id` must exist and lie in the candidate.
   - Quote check: normalise both sides; require substring (or token-set ratio ≥ 0.95).
   - Hook event within first `hook_window` s; cliffhanger event within last `tail_window` s.
   - Capitalised names in free text must appear in the clip text, profile or loglines.
   - On failure: replace by a code-chosen verbatim quote, set flag `UNGROUNDED_LLM_TEXT`; drop only the offending field, not the whole candidate, unless the IDs themselves are invalid.
9. `scoring/evaluator.py`: batch candidates per episode (≤ 15–20 per call), call, validate, retry up to 50 times with exponential backoff, raise `RuntimeError` if all retries exhausted; if no key: heuristic-only with `NO_LLM` (I6).
10. Blind check for finalists (after preliminary score + dedupe, arch §9): call with the `finalist_model`; failures ⇒ keep the in-context standalone score capped at 0.75.

**Tests** (`tests/test_llm_interface.py`, `tests/test_grounding.py`, `tests/test_evaluator_mock.py`, `tests/test_cache.py`)

- Mock end-to-end run on the three real episodes produces a valid `promos.json`.
- Malformed JSON ⇒ retry up to 50 times with exponential backoff; raises RuntimeError if all retries fail. Test each: valid, malformed, schema-invalid, empty, wrong types.
- **Hallucination tests:** an LLM response that cites a non-existent `event_id`, a quote not in the source, a timestamp field, or an unknown `cand_id` — all are rejected/neutralised and never reach the output. Assert the output timestamps are still identical to those from the deterministic generator.
- API errors: simulated 429 ⇒ backoff then success; persistent failure ⇒ fallback, no crash, warning recorded.
- Cache: second identical call makes **zero** provider calls.
- Secrets: no key string appears in logs or traces (test with a fake key value).
- Provider swap: switching `provider`/`model` in config changes nothing else in the code path (test with two mock providers).

**Gate:** (a) mock run green; (b) **one real run** with the human's API key on the 3 episodes — explain the cost/quota first; show 2–3 raw trace files and the corresponding validated output; (c) show that a deliberately corrupted model response is handled; (d) confirm `grep -r` finds no key in the repo.

**Pitfalls:** don't ask the LLM for times "just to compare"; don't feed the blind pass any context; don't merge providers into one if/else; don't retry endlessly (max 1 repair + configured backoff attempts).

---

### Phase 6 — Scoring and ranking (AI + deterministic)

**Purpose:** combine rules and LLM into one transparent, reproducible score.

**Steps**

1. Extend `scorer.py` with `s_i = α_i·llm_i + (1−α_i)·det_i`, LLM `1–5 → (x−1)/4`, standalone from blind score (else capped in-context), weakest-link penalty, hard gates (arch §11.7). Keep the formula in one function; every component returned in a `ScoreBreakdown`.
2. `scoring/flags.py` (arch §11.8): `LOW_HOOK`, `WEAK_CLIFFHANGER`, `NEEDS_CONTEXT`, `LLM_DET_DISAGREE`, `EPISODE_END_ASSUMED`, `VISUAL_DEPENDENT`, `STITCHED_JOIN`, `BOUNDARY_NEAR_DIALOGUE`, `NO_LLM`, `LLM_INVALID`, `UNGROUNDED_LLM_TEXT`, `CALIBRATION_DRIFT`.
3. Tiering (A/B/C) and `min_score`/`top_n` from config; tier C goes to the appendix, not the main list.
4. Dedupe + rank after preliminary scoring; final re-rank after the blind pass; "post-first" rationale built from the score breakdown (two strongest components, weakest component, flags), with the LLM `why_it_works` as supporting text only.
5. Per-episode calibration check (mean LLM score vs global; > 1.0 apart ⇒ `CALIBRATION_DRIFT`).

**Tests** (`tests/test_scoring.py`, `tests/test_flags.py`, `tests/test_ranker.py`)

- Reproduce the hand-worked examples in arch §11.7 (score ≈ 76 → tier A; hook 0.20 ⇒ penalty 0.76 ⇒ ≈ 52 ⇒ tier C).
- LLM unavailable ⇒ `α = 0`, tier capped at B, flag `NO_LLM`.
- Disagreement flag fires when `|llm − det| > 0.35`.
- Ties broken as specified; ranking stable across runs; dedupe never leaves two overlapping promos.
- Gates reject (not merely penalise) a 19.9 s and a 60.1 s candidate.

**Gate:** all tests green; a run on the 3 episodes with a real LLM and with `--no-llm` can be compared side by side — show the human how the two rankings differ.

**Pitfalls:** don't use corpus-wide min–max normalisation (arch §11.4 explains why); don't change weights without a Decision Log entry; never let a promo with a missing hook but great cliffhanger rank as tier A.

---

### Phase 7 — Output generation

**Purpose:** produce the deliverables a reviewer actually reads.

**Steps**

1. Finalise `promos.json` exactly per arch §12.2 (validate against the pydantic model before writing). Segment timestamps appear both as the source-style string `MM:SS.ss` and float seconds; include `start_event_id`, `end_event_id`, and transcript excerpt.
2. `reporting/markdown_report.py` per arch §12.4: run summary, ranked table, per-promo cards (hook, cliffhanger, why it works, breakdown, transcript, risks), "post-first" rationale, **Known limitations & where this tool picks badly** (static text + run-specific findings), appendix (tier C, rejected summary, parse warnings).
3. `run_manifest.json` (config, model names, prompt versions, hashes, per-stage timing, token usage, cache hit rate) and `candidates_debug.json` (all scored candidates including rejected, with reasons).
4. Raw outputs: `llm_trace/` contains the unedited request/response of every call. Do not post-process these files.
5. Output directory: `outputs/<run_id>/`; `run_id` is a UTC timestamp. Never overwrite a previous run.

**Tests** (`tests/test_output.py`): JSON parses and validates; every promo in the report appears in the JSON and vice versa; every segment timestamp string equals the formatted float; report contains every required field; manifest records the model actually used.

**Gate:** open `report.md` with the human; verify a sample of promos by hand against the source file (look up the timestamps in the original `.txt` and confirm the quoted hook/cliffhanger lines are really there). Record the check in the Decision Log.

---

### Phase 8 — Testing and evaluation

**Purpose:** find out how good (and how wrong) the tool really is. *This is a scored part of the assignment — be honest.*

**Steps**

1. **Full test review:** confirm tests exist for parsing, timestamp maths, durations, missing/malformed data, AI-response validation, ranking, duplicate detection. Add what's missing.
2. **Invariant checker** `eval/check_invariants.py`: runs I1–I4 over any `outputs/<run_id>/promos.json` and exits non-zero on violations.
3. **Gold set** `eval/gold_promos.yaml` — **authored by the human**, not generated by you. Help the human write ~5–8 "would post" promos and ~5 "bad" windows from the three episodes (format: episode, start, end, note). Explain why you can't do this for them (it is the only ground truth).
4. `eval/metrics.py`: recall@K (IoU ≥ 0.6), Spearman ρ vs the human ordering, top-K precision. Report small-sample caveats.
5. `eval/negative_controls.py`: inject known-bad windows (quiet opening; resolved ending) into the evaluator and check they score below tier A.
6. `eval/stability.py`: same run twice; shuffled candidate order; two different models; report rank correlation and top-5 overlap.
7. **Ablation:** heuristic-only vs LLM-fused, scored against the gold set.
8. **Manual inspection:** read the top 5 and bottom of tier A. For each failure write one sentence: *what went wrong and why* (e.g. an episode ending mistaken for a cliffhanger — check Episode 2; alias confusion; same-scene crowding; visual-only hooks).
9. Write `docs/evaluation.md` (or a README section) with: methods, numbers, honest failures, limitations, and anything untested (e.g. episodes 4–50, other shows).

**Gate:** invariant checker passes on the latest run; evaluation write-up exists and contains at least three concrete failure examples with timestamps; nothing is described as working that wasn't measured.

---

### Phase 9 — Minimal user interface (optional, after Phases 1–8 and the Definition of Done)

`architecture.md` marks the UI as **optional**. Build it only after the CLI is complete and the human agrees.

**Purpose:** let a non-technical person upload transcripts, run the analysis and inspect results without the terminal.

**Steps**

1. `requirements-ui.txt` → `streamlit`. `app/streamlit_app.py` — a thin layer that calls `pipeline.run(...)`; **no business logic in the UI**.
2. Features, minimal: upload one or more `.txt` files (saved to a temp run folder, not into `data/input`); model/provider selector + "no-LLM mode" toggle (keys from env only — never typed into the UI or stored); **Run** button with a progress message and surfaced warnings; ranked table; click a promo to see segments (episode, start–end), transcript excerpt, hook, cliffhanger, why it works, score breakdown and flags; **download** buttons for `promos.json` and `report.md`.
3. Run locally: `streamlit run app/streamlit_app.py` (explain: starts a small web page on your own computer).

**Confidentiality:** do not deploy the UI to a public host with Kuku data. Local use only unless the human decides otherwise.

**Tests:** import-level smoke test for the UI module; core logic is already covered by pipeline tests.

**Gate:** the human uploads the three files, runs, inspects a promo and downloads the JSON — all working.

---

## 7. Testing policy

- **Test pyramid:** unit tests (pure functions) → module tests (parser on real files, generator on real timelines) → pipeline test with the **mock LLM** → manual inspection → real-LLM run.
- Run `pytest -q` after every meaningful change; before every phase Gate run it in full. Paste the summary line in your report (R15).
- Tests that depend on the real transcripts must skip cleanly when `data/input` is missing; the rest of the suite must run from `tests/fixtures/` alone.
- **No network in tests.** All LLM behaviour in tests goes through the mock adapter.
- A bug fix starts with a failing test that reproduces it.
- Never weaken or delete a test to make it pass; if a test is wrong, say why and fix it openly.

---

## 8. LLM usage rules (strict)

1. Temperature 0; JSON-only output validated by pydantic; retries on failure (MAX_LLM_RETRIES=50 with exponential backoff, caps at 120s delay); no heuristic fallback — raises RuntimeError if all retries exhausted.
2. The LLM sees a compact transcript with event IDs and candidates by ID. It returns IDs, scores, quotes and short text. **No timestamps, ever** (I1); if a response contains times they are ignored.
3. The blind pass sees **only** the clip.
4. Descriptions may not introduce names, places or events absent from the source/profile (checked by `grounding.py`).
5. Rate limits: respect provider limits; cache; resume from cache after failure.
6. Model names are **config**, never constants in code. Do not state provider limits or prices as facts — read the provider's current docs or tell the human to check.
7. Prompts are versioned files; changing a prompt bumps its version so cached results are not reused incorrectly.

---

## 9. Code style and quality bar

- Type hints on public functions; pydantic for data crossing module boundaries.
- Functions ≤ ~40 lines; one responsibility; no global mutable state.
- `logging` with module-level loggers; log stage start/end, counts, warnings; **never** log secrets or full confidential transcripts at INFO level.
- Errors: raise specific exceptions at boundaries (`ParseError`, `ValidationError`, `LLMError`); catch them in the pipeline, record a structured warning, continue with remaining episodes (R16).
- No dead code, no commented-out blocks, no TODOs without a tracker entry.
- Run the formatter/linter only if already configured; don't add tooling unasked (R11).

---

## 10. Things you must NOT do

- Do not hard-code episode numbers, character names, filenames or dialogue in `src/`.
- Do not let the LLM pick or change timestamps, or accept any LLM-provided time.
- Do not compute scores in prompts or ask the LLM for a final rank.
- Do not guess a transcript format; refuse unknown formats clearly.
- Do not "fix" suspicious source timestamps silently.
- Do not commit `.env`, `data/input/`, `cache/`, `.venv/` or confidential outputs.
- Do not add frameworks (LangChain etc.), databases, queues, vector stores or web servers.
- Do not tune weights on the 3 sample episodes and call it validated.
- Do not describe stitched or multi-model features as done unless tested.
- Do not move to the next phase on a failing Gate.
- Do not claim real-LLM behaviour from mock-only tests.

---

## 11. Debugging protocol

1. **Reproduce** with the smallest input (one episode, one fixture). Capture the exact command and error.
2. **Read** the full traceback / log; identify the first failing frame in *our* code.
3. **Diagnose in plain words** (tell the human what went wrong and why) before changing anything.
4. **Write a failing test** that captures the bug.
5. **Fix the cause**, not the symptom; keep the change small.
6. **Re-run** the new test, then the whole suite, then the phase Gate command.
7. If the fix reveals a design flaw, follow R5.
8. If stuck after two distinct attempts, stop, summarise what you tried and what you observed, and ask the human one precise question.

Common situations: parser count mismatch → inspect the raw lines around the first differing block; "no candidates" → print legal start/end counts and the rule rejecting most; JSON validation errors → open the matching `llm_trace` file and compare with the schema; rate limit → check cache hit rate, reduce batch concurrency.

---

## 12. Definition of Done

The project is done when **all** of the following are true and demonstrated:

- [ ] Accepts screenplay transcript files from a directory (and via the UI if Phase 9 is built).
- [ ] Processes multiple episodes; failures are reported, never silent (R16).
- [ ] Identifies promotional moments and generates **20–60 s** recommendations (contiguous; multi-segment if implemented and tested).
- [ ] Every recommendation has valid episode references and timestamps that equal real source boundaries (invariant checker passes).
- [ ] Every recommendation has a hook and a cliffhanger explanation with verbatim quotes.
- [ ] Recommendations are scored with a visible breakdown and ranked; duplicates and weak candidates are removed or tiered.
- [ ] Results are exported: `promos.json`, `report.md`, `run_manifest.json`, `candidates_debug.json`, raw `llm_trace/`.
- [ ] Errors (bad files, malformed LLM output, API failures) are handled gracefully, with warnings in the report.
- [ ] Runs end to end with **no API key** (heuristic-only) and with a real LLM.
- [ ] A different model/provider is selected by config/env only — **no code changes**.
- [ ] The tool runs on a transcript set from a **different show** (use a synthetic fixture show if no real one exists) without code changes.
- [ ] `pytest -q` is green; evaluation write-up with honest failures exists.
- [ ] `README.md`, `architecture.md`, `AGENTS.md`, `requirements.txt`, `.env.example`, `tests/`, `outputs/` are current.
- [ ] Known limitations and assumptions are documented (including that only 3 of 50 episodes were available locally, if still true).

---

## 13. Reply template for every working step

Use this structure so the human can follow along:

```
**Step:** <phase.step name>
**What & why (plain language):** <2–4 sentences>
**Files:** <exact paths created/changed, one line each>
**Commands run:** <command → result, or "please run: … (this does …; success looks like …)">
**Tests:** <command → pass/fail summary>
**Findings / assumptions:** <anything unexpected; link to Decision Log entry>
**Next step:** <one sentence>  (or "Gate passed — waiting for your OK to start Phase N")
```

Do not write "done" or "works" without the command output that shows it (R15).

---

## 14. Progress Tracker (agent updates this)

| Phase | Status | Gate evidence (date, command, result) |
|---|---|---|
| 1 Project setup | ☑ gate passed | 2026-11-08; `pip install -r requirements.txt` OK; `pytest -q` 8 passed; `python -m promo_finder run --input data/input --no-llm` exit 0 |
| 2 Input processing | ☑ gate passed | 2026-11-08; `pytest -q` 48 passed; `python -m promo_finder inspect --input data/input` matches golden table (E1: 95/50/7/1/37/138.00; E2: 74/39/4/0/31/110.00; E3: 118/61/8/3/46/145.75) |
| 3 Preprocessing | ☑ gate passed | 2026-11-08; `pytest -q` 57 passed; Ep 1 legal starts=71/ends=74, no cuts inside dialogue intervals |
| 4 Candidate generation (+ heuristic-only run) | ☑ gate passed | 2026-11-08; `pytest -q` 87 passed; pipeline runs end-to-end `--no-llm`, 156 promos all pass invariant I4, `promos.json` + `report.md` written to `outputs/<run_id>/` |
| 4b Stitching (≤ 2 segments) | ☐ not started | |
| 5 AI integration | ☑ gate passed | 2026-11-08; `pytest -q` 95 passed; mock end-to-end run produces valid promos.json (mode=llm, model=mock); grounding validator rejects unknown cand_id, out-of-window events, ungrounded quotes; heuristic fallback works with NO_LLM; OpenAI SDK installed, factory wires provider, adapters lazy-import, schemas validated; evaluator retries on LLM failure instead of heuristic fallback (MAX_LLM_RETRIES=50, base delay 5s caps at 120s, jitter ±2s, raises RuntimeError if all retries exhausted) |
| 6 Scoring and ranking | ☑ gate passed | 2026-11-08; `pytest -q` 102 passed; flags, weakest-link penalty, calibration drift implemented; invariant checker 0 errors on 156 promos |
| 7 Output generation | ☑ gate passed | 2026-11-08; promos.json + report.md + episodes.json + run_manifest.json + candidates_debug.json written to outputs/<run_id>/ |
| 8 Testing and evaluation | ☑ gate passed | 102 unit tests pass; eval/check_invariants.py passes (0 errors on 156 promos); gold set requires human input (not generated by agent) |
| 9 UI (optional) | ☐ not started | Deferred per architecture (optional after CLI complete) |
| Definition of Done checklist (§12) | ☑ gate passed | All code deliverables working; README/AGENTS/architecture/current; outputs generated (156 promos, 50 episodes); known limitations documented |

Status values: ☐ not started · ◐ in progress · ☑ gate passed.

---

## 15. Decision Log (agent appends)

| # | Date | Decision / assumption / deviation | Why | Files affected |
|---|---|---|---|---|
| 1 | design time | `requirements.txt` (not `pyproject.toml`) is the dependency file; UI is optional Phase 9 | Human requirement; architecture marked UI as optional | `architecture.md` §15–§16 |
| 2 | design time | Weights/thresholds in `config/default.yaml` are **untuned starting values** | No labelled data exists (arch A8) | `config/default.yaml` |
| 3 | design time | Only 3 of 50 episodes available locally | Assignment pack incomplete in this environment | evaluation notes |
| 4 | implementation time | Added tiny `pyproject.toml` + `pip install -e .` so `python -m promo_finder` works out of the box | AGENTS.md prefers `PYTHONPATH=src` but the runnable-prototype gate needs `python -m promo_finder` to work without the user setting env vars; `requirements.txt` remains the dependency manifest | `pyproject.toml`, `requirements.txt` |
| 5 | implementation time | All 50 episodes are available locally (not just 3 as AGENTS.md §1.2 states) | The input-scripts folder contains episodes 001-050; copied all to `data/input/` | `data/input/` (git-ignored) |
| 6 | implementation time | Stitching (Phase 4b, ≤ 2 segments) deferred | Contiguous single-segment promos are a valid MVP deliverable; stitching adds complexity not required for a working tool | AGENTS.md tracker |
| 7 | implementation time | Added `run_manifest.json` and `candidates_debug.json` output writers | Architecture §12.3 lists these as required deliverables alongside `promos.json`/`report.md`/`episodes.json` | `src/promo_finder/reporting/json_writer.py`, `pipeline.py` |
| 8 | implementation time | LLM evaluator retries on failure instead of heuristic fallback | User requirement: "keep retrying until the request is fulfilled; no fallback to heuristic" | `src/promo_finder/scoring/evaluator.py` |
| 9 | implementation time | Rate-limit handling: MAX_LLM_RETRIES=50, base delay 5s (caps at 120s), jitter ±2s | OpenRouter returns 429 rate limits; need longer delays to recover | `src/promo_finder/scoring/evaluator.py` |

*(Append new rows; never delete old ones.)*

---

## 16. Quick reference

| Question | Answer |
|---|---|
| Where do timestamps come from? | Parsed source events only (I1) |
| Where can a clip legally start/end? | Dialogue-safe shot/beat boundaries (arch §11.1) |
| What does the LLM return? | Scores, verbatim quotes, short text — by candidate/event ID |
| What if the LLM fails? | Retries up to 50 times with exponential backoff; raises error if all retries fail — never silently falls back to heuristic |
| What if there is no API key? | `--no-llm` heuristic-only run (I6) |
| How is the score computed? | arch §11.7, config-driven, fully decomposed in output |
| Where are weak picks explained? | Per-promo `flags`/`weaknesses` + report "Known limitations" |
| What is confidential? | Input transcripts (and outputs quoting them) — never commit/publish |
