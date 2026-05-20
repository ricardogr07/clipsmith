"""LLM provider factory."""

from __future__ import annotations

from ..settings import AppConfig, Secrets
from .anthropic_provider import AnthropicProvider
from .base import ClipPick, ClipPicker
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider


def get_provider(config: AppConfig, secrets: Secrets, prompt_version: str = "v1") -> ClipPicker:
    """Return the configured LLM provider."""
    provider = config.llm.provider
    if provider == "anthropic":
        return AnthropicProvider(
            secrets.anthropic_api_key,
            model=config.llm.model_anthropic,
            retry_cfg=config.llm.retry,
            prompt_version=prompt_version,
        )
    if provider == "openai":
        return OpenAIProvider(
            secrets.openai_api_key,
            model=config.llm.model_openai,
            retry_cfg=config.llm.retry,
            prompt_version=prompt_version,
        )
    if provider == "ollama":
        return OllamaProvider(
            model=config.llm.model_ollama,
            retry_cfg=config.llm.retry,
            prompt_version=prompt_version,
        )
    raise ValueError(f"Unknown LLM provider: {provider!r}")


__all__ = [
    "ClipPick",
    "ClipPicker",
    "AnthropicProvider",
    "OpenAIProvider",
    "OllamaProvider",
    "get_provider",
]
