"""Typed configuration: YAML for behavior, .env for secrets."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ClipConfig(BaseModel):
    min_seconds: int = 15
    max_seconds: int = 30
    preroll_s: int = 25
    postroll_s: int = 10


class CandidatesConfig(BaseModel):
    density_window_s: int = 15
    density_peak_multiplier: float = 4.0
    existing_clip_boost: float = 100.0
    clip_command_boost: float = 25.0
    dedupe_window_s: int = 60


class TranscribeConfig(BaseModel):
    model: str = "medium"
    compute_type: str = "int8"
    language: str = "es"


class LLMConfig(BaseModel):
    provider: Literal["openai", "anthropic", "ollama"] = "anthropic"
    model_anthropic: str = "claude-sonnet-4-6"
    model_openai: str = "gpt-4.1"
    model_ollama: str = "llama3.1"


class CaptionConfig(BaseModel):
    font: str = "Arial"
    font_size: int = 72   # ASS pts at 1080×1920; 72 ≈ TikTok-style captions
    outline: int = 3
    position: str = "bottom"


class ReframeConfig(BaseModel):
    mode: Literal["center", "webcam", "face", "none"] = "center"
    webcam_rect: list[int] | None = None


class AppConfig(BaseModel):
    channels: list[str] = Field(default_factory=list)
    poll_interval_s: int = 120
    work_dir: Path = Path("./work")
    out_dir: Path = Path("./out")
    clip: ClipConfig = ClipConfig()
    candidates: CandidatesConfig = CandidatesConfig()
    transcribe: TranscribeConfig = TranscribeConfig()
    llm: LLMConfig = LLMConfig()
    caption: CaptionConfig = CaptionConfig()
    reframe: ReframeConfig = ReframeConfig()


class Secrets(BaseSettings):
    """Loaded from environment / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    twitch_client_id: str = ""
    twitch_client_secret: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    p = Path(path)
    data = yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}
    return AppConfig.model_validate(data or {})


def load_secrets() -> Secrets:
    return Secrets()
