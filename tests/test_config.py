"""Tests for the config loader (Phase 1 gate)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from promo_finder.config import load_config, overlay_env, load_yaml

CONFIG_PATH = "config/default.yaml"


def test_valid_config_loads():
    cfg = load_config(CONFIG_PATH)
    assert cfg.top_n == 10
    assert abs(sum(cfg.weights.values()) - 1.0) < 1e-6
    assert cfg.cut_rules.min_dur == 20.0
    assert cfg.cut_rules.max_dur == 60.0
    assert cfg.llm.provider == "mock"


def test_env_override_provider(monkeypatch):
    monkeypatch.setenv("PROMO_LLM_PROVIDER", "gemini")
    monkeypatch.setenv("PROMO_LLM_MODEL", "gemini-1.5-pro")
    data = overlay_env({"llm": {"provider": "mock", "eval_model": "mock"}})
    assert data["llm"]["provider"] == "gemini"
    assert data["llm"]["eval_model"] == "gemini-1.5-pro"


def test_missing_config_raises_clear_error():
    with pytest.raises(FileNotFoundError):
        load_config("config/does_not_exist.yaml")


def test_invalid_weights_raise():
    import yaml
    from promo_finder.config import Settings

    bad = {
        "weights": {"hook": 0.5, "cliffhanger": 0.5},  # sums to 1.0 but missing keys is fine
    }
    # weights that don't sum to 1
    bad_weights = {"hook": 0.9, "cliffhanger": 0.2}  # sums to 1.1
    with pytest.raises(Exception):
        Settings.model_validate(bad_weights)


def test_keys_not_in_repr():
    cfg = load_config(CONFIG_PATH)
    rep = repr(cfg)
    assert "GEMINI" not in rep.upper()
    assert "API_KEY" not in rep.upper()


def test_tier_order_validated():
    from pydantic import ValidationError
    from promo_finder.config import TierConfig

    with pytest.raises(ValidationError):
        TierConfig(A=50, B=80)  # A < B


def test_duration_order_validated():
    from pydantic import ValidationError
    from promo_finder.config import DurationConfig

    with pytest.raises(ValidationError):
        DurationConfig(hard_min=20, hard_max=60, soft_min=50, soft_max=30)


def test_load_yaml_empty_returns_dict(tmp_path: Path):
    p = tmp_path / "empty.yaml"
    p.write_text("", encoding="utf-8")
    assert load_yaml(p) == {}
