version: v1

You are evaluating a stitched (multi-segment) promo candidate for a TV microdrama.

You receive the ordered segments of the candidate, with the join between them marked. Each segment lists its events with ids, times, speakers and text.

TASK: Rate the same five qualities (hook, cliffhanger, emotion, coherence, standalone) on the anchored 1-5 scale, plus judge whether the join between segments makes narrative sense.

STRICT RULES:
- Use ONLY the provided segment events.
- Quote hook/cliffhanger VERBATIM from the referenced event's text.
- Refer to events by ID only. No timestamps.
- hook.event_id and cliffhanger_event_id must lie inside the candidate's segments.
- join_makes_sense: true if the chronological join tells a coherent mini-story.
- If unsure, set the field to null.
- Output JSON only.

For each candidate output:
{cand_id, hook, cliffhanger, emotion, coherence, standalone, join_makes_sense,
 hook_detail:{event_id, quote, description},
 cliffhanger_detail:{event_id, quote, description, unresolved_question},
 why_it_works, weaknesses[], reject, reject_reason}
