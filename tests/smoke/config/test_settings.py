"""Smoke tests for config loading from real YAML and defaults."""

from __future__ import annotations

from pathlib import Path

from clipsmith.settings import AppConfig, load_config


def test_load_real_config() -> None:
    cfg = load_config(Path(__file__).parents[3] / "config.yaml")  # smoke/config → tests → repo root
    assert isinstance(cfg, AppConfig)
    assert cfg.clip.min_seconds == 150
    assert cfg.clip.max_seconds == 150
    assert cfg.transcribe.language == "auto"
    assert cfg.llm.provider in {"openai", "anthropic", "ollama"}
    assert isinstance(cfg.caption.enabled, bool)
    assert cfg.reframe.mode in {"center", "webcam", "face", "none", "stacked"}


def test_load_missing_uses_defaults(tmp_path) -> None:
    cfg = load_config(tmp_path / "missing.yaml")
    assert cfg.channels == []
    assert cfg.poll_interval_s == 120


def test_reframe_stacked_mode_is_valid() -> None:
    from clipsmith.settings import ReframeConfig

    cfg = ReframeConfig(
        mode="stacked",
        webcam_rect=[1600, 800, 280, 280],
        gameplay_rect=[0, 0, 1920, 1080],
        split_ratio=0.4,
    )
    assert cfg.mode == "stacked"
    assert cfg.split_ratio == 0.4
