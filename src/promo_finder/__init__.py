"""Promo Finder — AI-powered promo discovery for screenplay transcripts.

Deterministic core owns parsing, timestamps, cut points, durations, scoring
and ranking. The LLM owns only story judgement (hook/cliffhanger/emotion/
coherence/standalone), referenced by event IDs only.
"""

__version__ = "0.1.0"
