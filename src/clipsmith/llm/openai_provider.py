"""OpenAI provider. Automatic prompt caching applies when the prefix >= 1024 tokens.

Keeps system + stream_context at the front of every request so OpenAI's
automatic caching can reuse the stable prefix across candidates.
"""

from __future__ import annotations

import logging

from ..models.candidates import CandidateMoment
from .base import ClipPick
from .prompts import SYSTEM_PROMPT, build_candidate_prompt

log = logging.getLogger(__name__)


class OpenAIProvider:
    def __init__(self, api_key: str, *, model: str = "gpt-4.1"):
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for the OpenAI provider")
        try:
            import openai as _openai
        except ImportError as exc:
            raise ImportError("openai package required: pip install openai") from exc
        self._client = _openai.OpenAI(api_key=api_key)
        self._model = model

    def pick(
        self,
        transcript_window: str,
        candidate: CandidateMoment,
        stream_context: str,
    ) -> ClipPick | None:
        candidate_prompt = build_candidate_prompt(transcript_window, candidate)
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                max_tokens=512,
                response_format={"type": "json_object"},
                messages=[
                    # System prompt — stable prefix, auto-cached by OpenAI after first call.
                    {"role": "system", "content": SYSTEM_PROMPT},
                    # Stream context — second stable block, same per VOD.
                    {"role": "user", "content": stream_context},
                    {"role": "assistant", "content": "Understood. Ready to evaluate candidates."},
                    # Per-candidate prompt — varies each call.
                    {"role": "user", "content": candidate_prompt},
                ],
            )
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
            return ClipPick.from_json(text)
        except Exception as exc:
            log.warning("OpenAI pick failed for t=%.1f: %s", candidate.t_center, exc)
            return None
