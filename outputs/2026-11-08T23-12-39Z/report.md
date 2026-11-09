# Promo Finder — Ranked Recommendations

## Run summary
- Mode: llm
- Provider: openai
- Eval model: openai/gpt-oss-20b
- Total promos: 3
- Tiers: A=2, C=1

## Ranked table

| Rank | ID | Episode(s) | Segments | Duration | Score | Tier | Flags |
|------|----|------------|----------|----------|-------|------|-------|
| 1 | PRM-d6db78a8ccea | 1 | 00:46.80–01:14.30 | 27.5s | 83.0 | A | — |
| 2 | PRM-d838fa201119 | 1 | 01:06.50–01:47.30 | 40.8s | 75.8 | A | — |
| 3 | PRM-f54303787d1a | 1 | 00:21.80–00:54.60 | 32.8s | 49.5 | C | UNGROUNDED_LLM_TEXT |

## Per-promo cards

### Rank 1 — PRM-d6db78a8ccea (tier A, score 83.0)
- Episodes: 1
- Total duration: 27.5s
- Why it works: Heuristic hook/cliffhanger from detected beats; no LLM judgement available.
- Hook (0.0s in): “You knew this before I walked through those doors!” — Juliana confronts Gerald with a sharp accusation, immediately establishing high tension.
- Cliffhanger: “How long?” — Juliana ends with an unresolved question, leaving the audience hanging on the duration of the betrayal.
- Weaknesses: No LLM evaluation; scores are rule-based only.

### Rank 2 — PRM-d838fa201119 (tier A, score 75.8)
- Episodes: 1
- Total duration: 40.8s
- Why it works: Heuristic hook/cliffhanger from detected beats; no LLM judgement available.
- Hook (0.0s in): “People change their minds, sister.” — Lady in Gold Gown delivers an ominous line hinting at betrayal and shifting loyalties.
- Cliffhanger: “And I am what?” — Juliana confronts her identity and role after a heated confrontation, leaving the audience in suspense.
- Weaknesses: No LLM evaluation; scores are rule-based only.

### Rank 3 — PRM-f54303787d1a (tier C, score 49.5)
- Episodes: 1
- Total duration: 32.8s
- Why it works: Heuristic hook/cliffhanger from detected beats; no LLM judgement available.
- Hook (0.0s in): “What do you mean?” — Juliana, trembling and pleading, questions the situation, setting up emotional tension.
- Cliffhanger: “Close-up on Juliana's hands desperately clenching fistfuls of her white dress fabric.” — The clip ends with a close‑up of Juliana’s clenched fists, showing her anger and distress.
- Weaknesses: No LLM evaluation; scores are rule-based only.
- Flags: UNGROUNDED_LLM_TEXT

## Known limitations & where this tool picks badly

- **Heuristic-only mode:** no LLM evaluation was used, so hook and cliffhanger quality are rule-based estimates, not story judgements.
- **Text-only input:** the tool sees screenplay text and timestamps, not video, so purely visual hooks or cliffhangers may be under-scored.
- **Speaker aliases:** the same character may appear under different labels (e.g. MATRIARCH vs NOBLE MATRIARCH); descriptions may treat them as distinct.
- **Resolved endings:** an episode ending is treated as a soft cliffhanger prior, so a resolved finale may be over-scored (cf. architecture O12).
- **No diversity pass:** several top promos may come from the same scene or confrontation (MVP has overlap-dedupe but no cross-arc diversity).
- **Untuned weights:** scoring weights are starting values, not fitted to editor feedback (assumption A8).

