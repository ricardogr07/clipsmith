"""OpenAI provider. Automatic prompt caching applies when the prefix >= 1024 tokens.

Keeps system + stream_context at the front of every request so OpenAI's
automatic caching can reuse the stable prefix across candidates.
"""

from __future__ import annotations

import logging
import time

from ..models.candidates import CandidateMoment
from .base import ClipPick
from .prompts import SYSTEM_PROMPT, build_candidate_prompt
from .retry import build_retry, RetryConfig

log = logging.getLogger(__name__)


class OpenAIProvider:
    def __init__(
        self, api_key: str, *, model: str = "gpt-4.1", retry_cfg: RetryConfig | None = None
    ):
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for the OpenAI provider")
        try:
            import openai as _openai
        except ImportError as exc:
            raise ImportError("openai package required: pip install openai") from exc
        self._client = _openai.OpenAI(api_key=api_key)
        self._model = model
        self._retry_cfg = retry_cfg or RetryConfig()

    def pick(
        self,
        transcript_window: str,
        candidate: CandidateMoment,
        stream_context: str,
    ) -> ClipPick | None:
        candidate_id = f"{candidate.t_center:.1f}"
        candidate_prompt = build_candidate_prompt(transcript_window, candidate)
        t0 = time.monotonic()
        try:
            retry = build_retry(self._retry_cfg, candidate_id=candidate_id, provider="openai")
            response = None
            for attempt in retry:
                with attempt:
                    response = self._client.chat.completions.create(
                        model=self._model,
                        max_tokens=512,
                        response_format={"type": "json_object"},
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": stream_context},
                            {
                                "role": "assistant",
                                "content": "Understood. Ready to evaluate candidates.",
                            },
                            {"role": "user", "content": candidate_prompt},
                        ],
                    )
            assert response is not None
            text = response.choices[0].message.content or ""
            usage = response.usage
            if usage:
                cached = (
                    getattr(usage.prompt_tokens_details, "cached_tokens", 0)
                    if hasattr(usage, "prompt_tokens_details")
                    else 0
                )
                log.debug(
                    "OpenAI usage: prompt=%d cached=%d completion=%d",
                    usage.prompt_tokens,
                    cached,
                    usage.completion_tokens,
                )
            pick = ClipPick.from_json(text)
            log.info(
                "llm_pick provider=openai candidate=%s include=%s elapsed_ms=%d",
                candidate_id,
                pick.include,
                round((time.monotonic() - t0) * 1000),
            )
            return pick
        except Exception as exc:
            log.warning(
                "llm_failed provider=openai candidate=%s attempts=%d error=%s",
                candidate_id,
                self._retry_cfg.max_attempts,
                exc,
            )
            return None
