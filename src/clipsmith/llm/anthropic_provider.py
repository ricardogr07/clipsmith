"""Anthropic Claude provider with prompt caching.

The system prompt and stream-context block are marked cache_control=ephemeral,
so they are cached after the first call and reused for all subsequent candidates
within one VOD run — reducing cost ~10x on the stable prefix.
"""

from __future__ import annotations

import logging

from ..candidates import CandidateMoment
from .base import SYSTEM_PROMPT, ClipPick

log = logging.getLogger(__name__)


class AnthropicProvider:
    def __init__(self, api_key: str, *, model: str = "claude-sonnet-4-6"):
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for the Anthropic provider")
        try:
            import anthropic as _anthropic
        except ImportError as exc:
            raise ImportError(
                "anthropic package required: pip install anthropic"
            ) from exc
        self._client = _anthropic.Anthropic(api_key=api_key)
        self._model = model

    def pick(
        self,
        transcript_window: str,
        candidate: CandidateMoment,
        stream_context: str,
    ) -> ClipPick | None:
        candidate_prompt = _build_candidate_prompt(transcript_window, candidate)
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=512,
                # System prompt cached — identical across all candidates in one VOD.
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
                            # Stream context cached — same for every candidate.
                            {
                                "type": "text",
                                "text": stream_context,
                                "cache_control": {"type": "ephemeral"},
                            },
                            # Per-candidate prompt — varies every call.
                            {
                                "type": "text",
                                "text": candidate_prompt,
                            },
                        ],
                    }
                ],
            )
            usage = response.usage
            log.debug(
                "Anthropic usage: input=%d cached_read=%d cached_write=%d output=%d",
                usage.input_tokens,
                getattr(usage, "cache_read_input_tokens", 0),
                getattr(usage, "cache_creation_input_tokens", 0),
                usage.output_tokens,
            )
            text = next(
                (b.text for b in response.content if b.type == "text"), ""
            )
            return ClipPick.from_json(text)
        except Exception as exc:
            log.warning("Anthropic pick failed for t=%.1f: %s", candidate.t_center, exc)
            return None


def _build_candidate_prompt(transcript_window: str, candidate: CandidateMoment) -> str:
    signals = "\n".join(f"- {r}" for r in candidate.reasons)
    return (
        f"## Candidate moment\n"
        f"Center: t={candidate.t_center:.1f}s (VOD seconds)\n"
        f"Score: {candidate.score:.1f}\n"
        f"Signal sources: {', '.join(candidate.sources)}\n\n"
        f"### Viewer signals\n{signals}\n\n"
        f"### Transcript window (±60s around center)\n"
        f"{transcript_window}\n\n"
        f"Respond with JSON only."
    )
