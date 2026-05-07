"""Backward-compatible re-export shim. Import from config.models or config.loaders directly."""

from .config.loaders import Secrets, load_config, load_secrets
from .config.models import (
    AppConfig,
    CandidatesConfig,
    CaptionConfig,
    ClipConfig,
    CloudConfig,
    LLMConfig,
    ReframeConfig,
    TranscribeConfig,
)

__all__ = [
    "AppConfig",
    "CandidatesConfig",
    "CaptionConfig",
    "ClipConfig",
    "CloudConfig",
    "LLMConfig",
    "ReframeConfig",
    "Secrets",
    "TranscribeConfig",
    "load_config",
    "load_secrets",
]
