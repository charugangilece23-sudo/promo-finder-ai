version: v1

You are analyzing a TV microdrama series to build a show profile for promo selection.

You receive all episode loglines and continuity notes, plus the set of distinct speaker labels found in the transcripts.

TASK: Produce a concise show premise (2-3 sentences) synthesised from the loglines, and an alias map grouping speaker labels that refer to the same character.

RULES:
- Use ONLY the provided loglines/continuity notes and speaker labels.
- Mark any uncertain alias as null (never guess a character's real name).
- Speaker labels are inconsistent (e.g. MATRIARCH / NOBLE MATRIARCH may be the same person); group labels that clearly refer to the same role.
- Output JSON only.
