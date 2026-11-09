"""Configuration loader for Promo Finder.

Loads ``config/default.yaml`` (YAML), overlays environment variables, and
validates everything with a pydantic model. API keys are read only from the
environment and are never included in ``repr`` or logs.

Env var overlay (all optional):
    PROMO_LLM_PROVIDER, PROMO_LLM_MODEL, PROMO_FINALIST_MODEL,
    PROMO_LLM_TEMPERATURE, PROMO_OUTPUT_DIR
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DurationConfig(BaseModel):
    hard_min: float = Field(default=20.0, gt=0)
    hard_max: float = Field(default=60.0, gt=0)
    soft_min: float = Field(default=25.0, gt=0)
    soft_max: float = Field(default=45.0, gt=0)
    edge_score: float = Field(default=0.6, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _check_order(self) -> "DurationConfig":
        if not (self.hard_min <= self.soft_min <= self.soft_max <= self.hard_max):
            raise ValueError(
                "duration requires hard_min <= soft_min <= soft_max <= hard_max"
            )
        return self


class WeakestLinkConfig(BaseModel):
    dims: list[str] = Field(default=["hook", "cliffhanger", "standalone"])
    floor_penalty: float = Field(default=0.6, ge=0.0, le=1.0)
    knee: float = Field(default=0.5, ge=0.0, le=1.0)


class TierConfig(BaseModel):
    A: float = Field(default=75.0, ge=0.0, le=100.0)
    B: float = Field(default=60.0, ge=0.0, le=100.0)

    @model_validator(mode="after")
    def _check_order(self) -> "TierConfig":
        if self.A < self.B:
            raise ValueError("tiers require A >= B")
        return self


class LLMConfig(BaseModel):
    provider: str = Field(default="mock")
    eval_model: str = Field(default="mock")
    finalist_model: str | None = Field(default=None)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0)
    max_retries: int = Field(default=3, ge=0)
    base_url: str | None = Field(default=None)


class CutRuleConfig(BaseModel):
    lead_in: float = Field(default=1.5, ge=0.0)
    tail_hold: float = Field(default=1.5, ge=0.0)
    epsilon: float = Field(default=0.05, ge=0.0)
    min_dur: float = Field(default=20.0, gt=0)
    max_dur: float = Field(default=60.0, gt=0)

    @model_validator(mode="after")
    def _check_dur(self) -> "CutRuleConfig":
        if self.min_dur > self.max_dur:
            raise ValueError("min_dur must not exceed max_dur")
        return self


class PrefilterConfig(BaseModel):
    variants_per_cluster: int = Field(default=3, ge=1)
    clusters_per_episode: int = Field(default=6, ge=1)
    iou_threshold: float = Field(default=0.5, ge=0.0, le=1.0)


class Settings(BaseModel):
    """Validated application settings."""

    model_config = ConfigDict(extra="forbid")

    duration: DurationConfig = Field(default_factory=DurationConfig)
    weakest_link: WeakestLinkConfig = Field(default_factory=WeakestLinkConfig)
    tiers: TierConfig = Field(default_factory=TierConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    cut_rules: CutRuleConfig = Field(default_factory=CutRuleConfig)
    prefilter: PrefilterConfig = Field(default_factory=PrefilterConfig)
    weights: dict[str, float] = Field(
        default={
            "hook": 0.25,
            "cliffhanger": 0.25,
            "standalone": 0.20,
            "emotion": 0.15,
            "coherence": 0.10,
            "duration": 0.05,
        }
    )
    llm_share: dict[str, float] = Field(
        default={
            "hook": 0.5,
            "cliffhanger": 0.6,
            "standalone": 0.8,
            "emotion": 0.5,
            "coherence": 0.7,
        }
    )
    top_n: int = Field(default=10, ge=1)
    min_score: float = Field(default=0.0, ge=0.0, le=100.0)
    output_dir: str = Field(default="outputs")
    input_glob: str = Field(default="*.txt")

    @field_validator("weights")
    @classmethod
    def _weights_sum_to_one(cls, v: dict[str, float]) -> dict[str, float]:
        total = sum(v.values())
        if not (0.99 <= total <= 1.01):
            raise ValueError("weights must sum to 1.0")
        return v

    def __repr__(self) -> str:  # pragma: no cover - debug only
        # Never leak API keys or env values in repr.
        return f"Settings(llm={self.llm.provider!r}, top_n={self.top_n})"


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML file into a dict. Returns {} for an empty file."""
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file {path} must contain a YAML mapping")
    return data


def overlay_env(data: dict[str, Any]) -> dict[str, Any]:
    """Overlay environment variables onto the config dict (shallow keys only).

    Recognised env vars: PROMO_LLM_PROVIDER, PROMO_LLM_MODEL,
    PROMO_FINALIST_MODEL, PROMO_LLM_TEMPERATURE, PROMO_OUTPUT_DIR.
    Other env vars are ignored so secrets never leak into config sections.
    """
    env_map = {
        "PROMO_LLM_PROVIDER": ("llm", "provider"),
        "PROMO_LLM_MODEL": ("llm", "eval_model"),
        "PROMO_FINALIST_MODEL": ("llm", "finalist_model"),
        "PROMO_LLM_TEMPERATURE": ("llm", "temperature"),
        "PROMO_OUTPUT_DIR": ("output_dir",),
    }
    for env_var, path in env_map.items():
        value = os.environ.get(env_var)
        if value is None:
            continue
        # Convert temperature to float.
        if path[-1] == "temperature":
            try:
                value = float(value)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid {env_var}={value!r}: must be a number"
                ) from exc
        node = data
        for key in path[:-1]:
            node = node.setdefault(key, {})
        node[path[-1]] = value
    return data


def load_config(path: str | Path = "config/default.yaml") -> Settings:
    """Load and validate application settings from a YAML config file.

    Env vars override YAML values. Raises a clear error on missing file or
    invalid values. Secrets are never logged.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path.resolve()}. "
            "Create config/default.yaml (see requirements/README)."
        )
    data = load_yaml(config_path)
    data = overlay_env(data)
    try:
        return Settings.model_validate(data)
    except Exception as exc:  # pydantic ValidationError
        raise ValueError(f"Invalid config in {config_path}: {exc}") from exc
