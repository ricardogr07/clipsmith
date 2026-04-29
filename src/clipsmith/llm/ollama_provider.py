"""Ollama provider — stub for future local LLM support."""

from __future__ import annotations

from ..candidates import CandidateMoment
from .base import ClipPick


class OllamaProvider:
    def __init__(self, model: str = "llama3.1"):
        self._model = model

    def pick(
        self,
        transcript_window: str,
        candidate: CandidateMoment,
        stream_context: str,
    ) -> ClipPick | None:
        raise NotImplementedError(
            "Ollama provider is not yet implemented. "
            "Set llm.provider to 'anthropic' or 'openai' in config.yaml."
        )
