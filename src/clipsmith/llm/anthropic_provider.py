"""Anthropic Claude provider with prompt caching.

The system prompt and stream-context block are marked cache_control=ephemeral,
so they are cached after the first call and reused for all subsequent candidates
within one VOD run — reducing cost ~10x on the stable prefix.
"""

from __future__ import annotations

import logging
import time

from ..models.candidates import CandidateMoment
from .base import ClipPick
from .prompts import SYSTEM_PROMPT, build_candidate_prompt
from .retry import build_retry, RetryConfig

log = logging.getLogger(__name__)


class AnthropicProvider:
    def __init__(
        self,
        api_key: str,
        *,
        model: str = "claude-sonnet-4-6",
        retry_cfg: RetryConfig | None = None,
    ):
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for the Anthropic provider")
        try:
            import anthropic as _anthropic
        except ImportError as exc:
            raise ImportError("anthropic package required: pip install anthropic") from exc
        self._client = _anthropic.Anthropic(api_key=api_key)
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
            retry = build_retry(self._retry_cfg, candidate_id=candidate_id, provider="anthropic")
            response = None
            for attempt in retry:
                with attempt:
                    response = self._client.messages.create(
                        model=self._model,
                        max_tokens=512,
                        system=[
                            {
                                "type": "text",
                                "text": SYSTEM_PROMPT,
                                "cache_control": {"type": "ephemeral"},
                            }
                        ],
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": stream_context,
                                        "cache_control": {"type": "ephemeral"},
                                    },
                                    {
                                        "type": "text",
                                        "text": candidate_prompt,
                                    },
                                ],
                            }
                        ],
                    )
            assert response is not None
            usage = response.usage
            log.debug(
                "Anthropic usage: input=%d cached_read=%d cached_write=%d output=%d",
                usage.input_tokens,
                getattr(usage, "cache_read_input_tokens", 0),
                getattr(usage, "cache_creation_input_tokens", 0),
                usage.output_tokens,
            )
            text = next((b.text for b in response.content if b.type == "text"), "")  # type: ignore[union-attr]
            pick = ClipPick.from_json(text)
            log.info(
                "llm_pick provider=anthropic candidate=%s include=%s elapsed_ms=%d",
                candidate_id,
                pick.include,
                round((time.monotonic() - t0) * 1000),
            )
            return pick
        except Exception as exc:
            log.warning(
                "llm_failed provider=anthropic candidate=%s attempts=%d error=%s",
                candidate_id,
                self._retry_cfg.max_attempts,
                exc,
            )
            return None
