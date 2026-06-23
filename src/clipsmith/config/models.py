"""Pydantic configuration schema models — no I/O, no environment access."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class ClipConfig(BaseModel):
    min_seconds: int = 150
    max_seconds: int = 150
    preroll_s: int = 25
    postroll_s: int = 10
    min_clip_gap_s: int = 120  # minimum seconds between candidates sent to LLM


class CandidatesConfig(BaseModel):
    density_window_s: int = 15
    density_peak_multiplier: float = 4.0
    existing_clip_boost: float = 100.0
    clip_command_boost: float = 25.0
    dedupe_window_s: int = 60
    transcript_hype_score: float = 12.0
    audio_energy_enabled: bool = True
    audio_energy_window_s: float = 2.0
    audio_energy_peak_multiplier: float = 2.0
    audio_energy_boost: float = 15.0
    hype_keywords: list[str] = [
        "jaja",
        "jeje",
        "jajaj",
        "jajaja",
        "lmao",
        "lol",
        "xd",
        "xdd",
        "omg",
        "wow",
        "nooo",
        "noooo",
        "increíble",
        "increible",
        "tremendo",
        "brutal",
        "dios",
        "wtf",
        "carajo",
        "caray",
        "bestia",
        "monstro",
    ]


class TranscribeConfig(BaseModel):
    model: str = "medium"
    compute_type: str = "int8"
    language: str = "auto"  # "auto" → language=None to faster-whisper (auto-detect)
    chunk_minutes: int = 0  # 0 = disabled; >0 splits audio into N-minute chunks
    chunk_overlap_s: int = 30  # overlap between adjacent chunks to avoid boundary word loss
    max_workers: int = 4  # ThreadPoolExecutor concurrency for parallel transcription


class RetryConfig(BaseModel):
    max_attempts: int = 3
    wait_min_s: float = 1.0
    wait_max_s: float = 30.0
    multiplier: float = 2.0
    jitter: bool = True


class LLMConfig(BaseModel):
    provider: Literal["openai", "anthropic", "ollama"] = "anthropic"
    model_anthropic: str = "claude-sonnet-4-6"
    model_openai: str = "gpt-4.1"
    model_ollama: str = "llama3.1:8b"
    retry: RetryConfig = RetryConfig()


class CaptionConfig(BaseModel):
    enabled: bool = False
    font: str = "Arial"
    font_size: int = 72  # ASS pts at 1080×1920; 72 ≈ TikTok-style captions
    outline: int = 3
    position: str = "bottom"


class ReframeConfig(BaseModel):
    mode: Literal["center", "webcam", "face", "none", "stacked"] = "center"
    webcam_rect: list[int] | None = None
    gameplay_rect: list[int] | None = None
    split_ratio: float = Field(default=0.4, ge=0.01, le=0.99)


class CloudConfig(BaseModel):
    resource_group: str = (
        "clipsmith-rg"  # used by `status` command; runs get their own ephemeral rg
    )
    location: str = "eastus"
    aci_cpu: float = 4.0
    aci_memory_gb: float = 16.0
    docker_image: str = ""
    gpu_sku: str = ""  # e.g. "V100" — empty means CPU-only
    acr_login_server: str = ""
    acr_username: str = ""
    acr_password: str = ""
    key_vault_uri: str = ""
    secret_names: list[str] = []


class CheckpointConfig(BaseModel):
    enabled: bool = True
    dir: str = ".checkpoints"


class PublishConfig(BaseModel):
    youtube_credentials: str = "credentials.json"
    youtube_token: str = ".youtube_token.json"
    youtube_privacy: Literal["private", "unlisted", "public"] = "private"
    youtube_category: int = 20  # 20 = Gaming


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
    cloud: CloudConfig = CloudConfig()
    checkpoint: CheckpointConfig = CheckpointConfig()
    publish: PublishConfig = PublishConfig()
