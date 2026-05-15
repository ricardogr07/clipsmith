"""Ollama provider — free local LLM via ollama Python client."""

from __future__ import annotations

import logging
import time

from ..models.candidates import CandidateMoment
from .base import ClipPick
from .prompts import SYSTEM_PROMPT
from .retry import build_retry, RetryConfig

log = logging.getLogger(__name__)


class OllamaProvider:
    def __init__(self, model: str = "llama3.1:8b", retry_cfg: RetryConfig | None = None):
        self._model = model
        self._retry_cfg = retry_cfg or RetryConfig()

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

        candidate_id = f"{candidate.t_center:.1f}"
        user_msg = (
            f"Stream context:\n{stream_context}\n\n"
            f"Candidate center: {candidate.t_center:.1f}s  score={candidate.score:.1f}  "
            f"signals={','.join(candidate.sources)}\n\n"
            f"Transcript window:\n{transcript_window}"
        )
        t0 = time.monotonic()
        try:
            retry = build_retry(self._retry_cfg, candidate_id=candidate_id, provider="ollama")
            resp = None
            for attempt in retry:
                with attempt:
                    resp = ollama.chat(
                        model=self._model,
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_msg},
                        ],
                        format="json",
                    )
            assert resp is not None
            pick = ClipPick.from_json(resp.message.content or "")
            log.info(
                "llm_pick provider=ollama candidate=%s include=%s elapsed_ms=%d",
                candidate_id,
                pick.include,
                round((time.monotonic() - t0) * 1000),
            )
            return pick
        except Exception as exc:
            log.warning(
                "llm_failed provider=ollama candidate=%s attempts=%d error=%s",
                candidate_id,
                self._retry_cfg.max_attempts,
                exc,
            )
            return None
