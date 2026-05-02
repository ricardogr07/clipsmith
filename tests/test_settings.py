from pathlib import Path

from clipsmith.settings import AppConfig, load_config


def test_load_real_config():
    cfg = load_config(Path(__file__).parent.parent / "config.yaml")
    assert isinstance(cfg, AppConfig)
    assert cfg.clip.min_seconds == 15
    assert cfg.clip.max_seconds == 30
    assert cfg.transcribe.language == "es"
    assert cfg.llm.provider in {"openai", "anthropic", "ollama"}
    assert isinstance(cfg.caption.enabled, bool)
    assert cfg.reframe.mode in {"center", "webcam", "face", "none"}


def test_load_missing_uses_defaults(tmp_path):
    cfg = load_config(tmp_path / "missing.yaml")
    assert cfg.channels == []
    assert cfg.poll_interval_s == 120
