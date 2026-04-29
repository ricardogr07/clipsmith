"""LLM provider factory."""

from __future__ import annotations

from .anthropic_provider import AnthropicProvider
from .base import ClipPick, ClipPicker
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider


def get_provider(config, secrets) -> ClipPicker:  # type: ignore[type-arg]
    """Return the configured LLM provider."""
    from ..settings import AppConfig, Secrets

    provider = config.llm.provider
    if provider == "anthropic":
        return AnthropicProvider(secrets.anthropic_api_key, model=config.llm.model_anthropic)
    if provider == "openai":
        return OpenAIProvider(secrets.openai_api_key, model=config.llm.model_openai)
    if provider == "ollama":
        return OllamaProvider(model=config.llm.model_ollama)
    raise ValueError(f"Unknown LLM provider: {provider!r}")


__all__ = ["ClipPick", "ClipPicker", "AnthropicProvider", "OpenAIProvider", "OllamaProvider", "get_provider"]
