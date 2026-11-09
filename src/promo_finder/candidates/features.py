"""Deterministic promo features (architecture §11.4).

Each feature is a pure function returning a value in [0, 1], with its raw
inputs recorded for the debug dump. Lexicons live in
``config/lexicons/en.yaml`` (never hard-coded word lists in Python).

Deterministic features act as a sanity anchor for the LLM; they are
config-weighted and do not depend on the other candidates in the batch
(fixed transforms, not corpus min-max).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

import yaml

from promo_finder.models import Candidate, Event
from promo_finder.preprocess.timeline import Timeline


@lru_cache(maxsize=1)
def _load_lexicon(path: str = "config/lexicons/en.yaml") -> dict:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except FileNotFoundError:
        return {}


def _count_terms(text: str, terms: list[str]) -> int:
    low = text.lower()
    return sum(1 for term in terms if term.lower() in low)


@dataclass
class HookFeatures:
    speech_within_1s: float
    delivery_intensity: float
    shock_hits: float
    second_person: float
    exclamation_or_question: float
    quiet_opening_penalty: float


def hook_features(candidate: Candidate, timeline: Timeline,
                  lexicon: dict) -> HookFeatures:
    """Features for the hook (first ~3 s of the clip)."""
    seg = candidate.segments[0]
    start = seg.start
    window_end = start + 3.0

    # Events starting in the first 3 seconds.
    early = [e for e in timeline.events
             if start - 1e-9 <= e.start < window_end]
    dialogue_early = [e for e in early if e.kind.value == "dialogue"]
    speech_within_1s = 1.0 if any(
        e.start <= start + 1.0 for e in dialogue_early
    ) else 0.0

    # Peak delivery-tag intensity in the first 3 s.
    intensities = lexicon.get("delivery_intensities", {})
    peak = 0.0
    for e in dialogue_early:
        for tag in e.delivery:
            peak = max(peak, float(intensities.get(tag, 0.3)))
    delivery_intensity = min(1.0, peak)

    # Shock/reveal/command terms in early dialogue.
    early_text = " ".join(e.text for e in dialogue_early)
    shock = _count_terms(early_text, lexicon.get("shock_terms", []))
    shock_hits = min(1.0, shock / 3.0)

    second_person = min(1.0,
                        _count_terms(early_text,
                                     lexicon.get("second_person_terms", [])) / 2.0)

    exclamation_or_question = 1.0 if (
        "!" in early_text or "?" in early_text
    ) else 0.0

    # Penalty: quiet opening (only camera/establishing in first 3 s).
    has_action_or_dialogue = any(
        e.kind.value in ("dialogue", "action", "sfx") for e in early
    )
    quiet_opening_penalty = 0.0 if has_action_or_dialogue else 1.0

    return HookFeatures(
        speech_within_1s=speech_within_1s,
        delivery_intensity=delivery_intensity,
        shock_hits=shock_hits,
        second_person=second_person,
        exclamation_or_question=exclamation_or_question,
        quiet_opening_penalty=quiet_opening_penalty,
    )


def hook_score(hf: HookFeatures) -> float:
    """Combine hook features into [0, 1]."""
    score = (
        0.30 * hf.speech_within_1s
        + 0.25 * hf.delivery_intensity
        + 0.20 * hf.shock_hits
        + 0.15 * hf.second_person
        + 0.10 * hf.exclamation_or_question
    )
    score = score * (1.0 - 0.5 * hf.quiet_opening_penalty)
    return max(0.0, min(1.0, score))


@dataclass
class CliffhangerFeatures:
    final_is_question_or_ellipsis: float
    reveal_threat_hits: float
    next_beat_cut_off: float
    calm_resolution_penalty: float
    episode_end_bonus: float


def cliffhanger_features(candidate: Candidate, timeline: Timeline,
                         lexicon: dict) -> CliffhangerFeatures:
    """Features for the cliffhanger (last ~5 s of the clip)."""
    seg = candidate.segments[0]
    end = seg.end
    window_start = max(seg.start, end - 5.0)

    late = [e for e in timeline.events
            if window_start - 1e-9 <= e.start < end + 1e-9]
    dialogue_late = [e for e in late if e.kind.value == "dialogue"]

    final_text = dialogue_late[-1].text if dialogue_late else ""
    final_is_q_or_ellipsis = 1.0 if (
        final_text.strip().endswith("?") or "…" in final_text or "..." in final_text
    ) else 0.0

    reveal = _count_terms(final_text, lexicon.get("cliffhanger_terms", []))
    reveal_threat_hits = min(1.0, reveal / 3.0)

    # Next beat after the clip end is an answer/reaction that got cut off.
    next_beat = timeline.next_beat_after(end)
    next_beat_cut_off = 1.0 if next_beat is not None else 0.0

    # Penalty: final beat is a calm resolution.
    resolution = _count_terms(final_text, lexicon.get("resolution_terms", []))
    calm_resolution_penalty = 1.0 if resolution > 0 else 0.0

    # Episode-end bonus (soft prior, never automatic).
    episode_end_bonus = 1.0 if abs(end - timeline.duration) < 1e-9 else 0.0

    return CliffhangerFeatures(
        final_is_question_or_ellipsis=final_is_q_or_ellipsis,
        reveal_threat_hits=reveal_threat_hits,
        next_beat_cut_off=next_beat_cut_off,
        calm_resolution_penalty=calm_resolution_penalty,
        episode_end_bonus=episode_end_bonus,
    )


def cliffhanger_score(cf: CliffhangerFeatures) -> float:
    score = (
        0.30 * cf.final_is_question_or_ellipsis
        + 0.25 * cf.reveal_threat_hits
        + 0.25 * cf.next_beat_cut_off
        + 0.10 * cf.episode_end_bonus
    )
    score = score * (1.0 - 0.5 * cf.calm_resolution_penalty)
    return max(0.0, min(1.0, score))


@dataclass
class EmotionFeatures:
    peak_delivery_intensity: float
    mean_delivery_intensity: float
    speaker_alternations: float
    words_per_sec: float
    exclamation_density: float


def emotion_features(candidate: Candidate, timeline: Timeline,
                     lexicon: dict) -> EmotionFeatures:
    """Emotion/intensity features across the whole clip."""
    seg = candidate.segments[0]
    inside = [e for e in timeline.events
              if seg.start - 1e-9 <= e.start and e.end <= seg.end + 1e-9]
    dialogue = [e for e in inside if e.kind.value == "dialogue"]

    intensities = lexicon.get("delivery_intensities", {})
    vals = []
    for e in dialogue:
        for tag in e.delivery:
            vals.append(float(intensities.get(tag, 0.3)))
    peak = max(vals) if vals else 0.0
    mean = (sum(vals) / len(vals)) if vals else 0.0

    # Speaker alternations (conflict density).
    speakers = [e.speaker_raw for e in dialogue if e.speaker_raw]
    alternations = 0
    for a, b in zip(speakers, speakers[1:]):
        if a != b:
            alternations += 1
    speaker_alternations = min(1.0, alternations / 4.0)

    duration = seg.end - seg.start
    total_words = sum(len(re.findall(r"\S+", e.text)) for e in dialogue)
    words_per_sec = min(1.0, (total_words / duration) / 6.0) if duration > 0 else 0.0

    all_text = " ".join(e.text for e in inside)
    exclamations = all_text.count("!")
    exclamation_density = min(1.0, exclamations / 3.0)

    return EmotionFeatures(
        peak_delivery_intensity=peak,
        mean_delivery_intensity=mean,
        speaker_alternations=speaker_alternations,
        words_per_sec=words_per_sec,
        exclamation_density=exclamation_density,
    )


def emotion_score(ef: EmotionFeatures) -> float:
    return max(0.0, min(1.0, (
        0.35 * ef.peak_delivery_intensity
        + 0.25 * ef.mean_delivery_intensity
        + 0.20 * ef.speaker_alternations
        + 0.10 * ef.words_per_sec
        + 0.10 * ef.exclamation_density
    )))


@dataclass
class CoherenceFeatures:
    scene_crossings: float
    mid_dialogue_cuts: float  # always 0 by construction


def coherence_features(candidate: Candidate, timeline: Timeline) -> CoherenceFeatures:
    """Deterministic coherence: scene-boundary crossings."""
    seg = candidate.segments[0]
    # Count distinct scenes touched by events inside the window.
    inside = [e for e in timeline.events
              if seg.start - 1e-9 <= e.start and e.end <= seg.end + 1e-9]
    scenes = {e.scene for e in inside if e.scene is not None}
    scene_crossings = min(1.0, max(0, len(scenes) - 1) / 2.0)
    # Mid-dialogue cuts are always 0 (guaranteed by cut points).
    return CoherenceFeatures(
        scene_crossings=scene_crossings,
        mid_dialogue_cuts=0.0,
    )


def coherence_score(cf: CoherenceFeatures) -> float:
    # Fewer scene crossings = more coherent.
    return max(0.0, 1.0 - 0.5 * cf.scene_crossings)


@dataclass
class StandaloneFeatures:
    distinct_speakers: float
    opening_not_pronoun_only: float
    speakers_named_in_clip: float


def standalone_features(candidate: Candidate, timeline: Timeline) -> StandaloneFeatures:
    """Deterministic standalone proxy (blind pass dominates)."""
    seg = candidate.segments[0]
    inside = [e for e in timeline.events
              if seg.start - 1e-9 <= e.start and e.end <= seg.end + 1e-9]
    dialogue = [e for e in inside if e.kind.value == "dialogue"]
    speakers = {e.speaker_raw for e in dialogue if e.speaker_raw}
    distinct_speakers = min(1.0, len(speakers) / 2.0)

    first = dialogue[0].text if dialogue else ""
    opening_not_pronoun_only = 0.0
    if first:
        stripped = first.strip()
        # A pronoun/question-word-only opener ("You knew?", "Why?", "And you knew?")
        # is a weak opener because it needs prior context.
        pronoun_only = bool(re.fullmatch(
            r"\s*(?:and\s+|but\s+|so\s+)?(you|he|she|it|they|i|we|why|what|how|who)\b[^A-Za-z0-9]*\??\s*",
            stripped, re.IGNORECASE))
        opening_not_pronoun_only = 0.0 if pronoun_only else 1.0

    speakers_named_in_clip = distinct_speakers  # names appear in speaker labels

    return StandaloneFeatures(
        distinct_speakers=distinct_speakers,
        opening_not_pronoun_only=opening_not_pronoun_only,
        speakers_named_in_clip=speakers_named_in_clip,
    )


def standalone_det_score(sf: StandaloneFeatures) -> float:
    return max(0.0, min(1.0, (
        0.5 * sf.distinct_speakers
        + 0.3 * sf.opening_not_pronoun_only
        + 0.2 * sf.speakers_named_in_clip
    )))


@dataclass
class DurationFeatures:
    seconds: float
    in_hard_range: bool
    plateau: float


def duration_features(candidate: Candidate) -> DurationFeatures:
    secs = candidate.duration
    in_hard = 20.0 <= secs <= 60.0
    # Soft plateau 25-45 = full score, tapering toward the hard edges.
    if 25.0 <= secs <= 45.0:
        plateau = 1.0
    elif 20.0 <= secs < 25.0:
        plateau = 0.6 + 0.4 * (secs - 20.0) / 5.0
    elif 45.0 < secs <= 60.0:
        plateau = 1.0 - 0.4 * (secs - 45.0) / 15.0
    else:
        plateau = 0.0
    return DurationFeatures(seconds=secs, in_hard_range=in_hard,
                            plateau=plateau)


def duration_combined(df: DurationFeatures, edge_score: float = 0.6) -> float:
    if not df.in_hard_range:
        return 0.0  # hard gate applied by scorer; here just report plateau
    return df.plateau


def extract_all_features(candidate: Candidate, timeline: Timeline,
                         lexicon: dict | None = None) -> dict:
    """Run every deterministic feature and return a debug-friendly dict."""
    if lexicon is None:
        lexicon = _load_lexicon()

    hf = hook_features(candidate, timeline, lexicon)
    cf_ = cliffhanger_features(candidate, timeline, lexicon)
    ef = emotion_features(candidate, timeline, lexicon)
    coh = coherence_features(candidate, timeline)
    sf = standalone_features(candidate, timeline)
    df = duration_features(candidate)

    return {
        "hook": {"features": hf.__dict__, "score": hook_score(hf)},
        "cliffhanger": {"features": cf_.__dict__, "score": cliffhanger_score(cf_)},
        "emotion": {"features": ef.__dict__, "score": emotion_score(ef)},
        "coherence": {"features": coh.__dict__, "score": coherence_score(coh)},
        "standalone": {"features": sf.__dict__, "score": standalone_det_score(sf)},
        "duration": {"features": df.__dict__, "score": duration_combined(df)},
    }
