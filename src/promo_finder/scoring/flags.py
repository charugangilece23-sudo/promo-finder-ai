"""Risk flags (architecture §11.8).

Each flag explains where a recommendation may be wrong, supporting the
"where does this tool pick badly?" transparency requirement.
"""

from __future__ import annotations

LOW_HOOK = "LOW_HOOK"
WEAK_CLIFFHANGER = "WEAK_CLIFFHANGER"
NEEDS_CONTEXT = "NEEDS_CONTEXT"
LLM_DET_DISAGREE = "LLM_DET_DISAGREE"
EPISODE_END_ASSUMED = "EPISODE_END_ASSUMED"
VISUAL_DEPENDENT = "VISUAL_DEPENDENT"
STITCHED_JOIN = "STITCHED_JOIN"
BOUNDARY_NEAR_DIALOGUE = "BOUNDARY_NEAR_DIALOGUE"
NO_LLM = "NO_LLM"
LLM_INVALID = "LLM_INVALID"
UNGROUNDED_LLM_TEXT = "UNGROUNDED_LLM_TEXT"
CALIBRATION_DRIFT = "CALIBRATION_DRIFT"


def compute_flags(
    feats: dict,
    llm_eval: dict | None,
    combined: dict[str, float],
    candidate,
    timeline,
    settings,
    no_llm: bool = False,
) -> list[str]:
    """Compute the risk flags for a candidate.

    Pure function: same inputs always yield the same flags (I7).
    """
    flags: list[str] = []

    if no_llm:
        flags.append(NO_LLM)

    # LOW_HOOK / WEAK_CLIFFHANGER: dimension < 0.5.
    if feats.get("hook", {}).get("score", 0.0) < 0.5:
        flags.append(LOW_HOOK)
    if feats.get("cliffhanger", {}).get("score", 0.0) < 0.5:
        flags.append(WEAK_CLIFFHANGER)

    # LLM_DET_DISAGREE: |llm - det| > 0.35 on any dimension.
    if llm_eval and "scores" in llm_eval:
        for dim in ("hook", "cliffhanger", "standalone", "emotion", "coherence"):
            det = feats.get(dim, {}).get("score", 0.0)
            llm = llm_eval["scores"].get(dim)
            if llm is not None and abs(llm - det) > 0.35:
                flags.append(LLM_DET_DISAGREE)
                break

    # EPISODE_END_ASSUMED: cliffhanger relies mainly on episode-end bonus.
    cf_ = feats.get("cliffhanger", {}).get("features", {})
    if cf_.get("episode_end_bonus", 0.0) > 0 and cf_.get("final_is_question_or_ellipsis", 0.0) == 0:
        flags.append(EPISODE_END_ASSUMED)

    # NEEDS_CONTEXT: standalone low.
    if feats.get("standalone", {}).get("score", 0.0) < 0.4:
        flags.append(NEEDS_CONTEXT)

    # VISUAL_DEPENDENT: hook/cliffhanger from camera/action rather than speech.
    hf = feats.get("hook", {}).get("features", {})
    if hf.get("speech_within_1s", 0.0) == 0 and hf.get("shock_hits", 0) == 0:
        flags.append(VISUAL_DEPENDENT)

    # LLM text issues.
    if llm_eval and llm_eval.get("_flags"):
        for f in llm_eval["_flags"]:
            if f not in flags:
                flags.append(f)

    return flags


def calibration_drift(episode_llm_means: dict[int, float],
                      global_mean: float,
                      threshold: float = 1.0) -> list[int]:
    """Return episode numbers whose mean LLM score drifts from global > threshold.

    Used to flag CALIBRATION_DRIFT per episode (§11.7).
    """
    drifting: list[int] = []
    for ep, mean in episode_llm_means.items():
        if abs(mean - global_mean) > threshold:
            drifting.append(ep)
    return drifting
