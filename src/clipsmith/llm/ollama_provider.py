"""Ollama provider — free local LLM via ollama Python client."""

from __future__ import annotations

import logging

from ..candidates import CandidateMoment
from .base import ClipPick, SYSTEM_PROMPT

log = logging.getLogger(__name__)


class OllamaProvider:
    def __init__(self, model: str = "llama3.1:8b"):
        self._model = model

    def pick(
        self,
        transcript_window: str,
        candidate: CandidateMoment,
        stream_context: str,
    ) -> ClipPick | None:
        try:
            import ollama
        except ImportError as exc:
            raise RuntimeError(
                'ollama package required: pip install ".[ollama]"  '
                "then pull a model: ollama pull llama3.1:8b"
            ) from exc

        user_msg = (
            f"Stream context:\n{stream_context}\n\n"
            f"Candidate center: {candidate.t_center:.1f}s  score={candidate.score:.1f}  "
            f"signals={','.join(candidate.sources)}\n\n"
            f"Transcript window:\n{transcript_window}"
        )
        try:
            resp = ollama.chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                format="json",
            )
            return ClipPick.from_json(resp.message.content or "")
        except Exception as exc:
            log.warning("ollama pick failed (%s): %s", self._model, exc)
            return None
