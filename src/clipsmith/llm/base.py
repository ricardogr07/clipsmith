"""Shared types and Protocol for clip-picker LLM providers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Protocol, runtime_checkable

from ..candidates import CandidateMoment


@dataclass
class ClipPick:
    include: bool
    start_offset_s: float
    end_offset_s: float
    title_es: str
    reason: str

    # Duration convenience.
    @property
    def duration_s(self) -> float:
        return self.end_offset_s - self.start_offset_s

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ClipPick":
        return cls(
            include=bool(d.get("include", False)),
            start_offset_s=float(d.get("start_offset_s", 0.0)),
            end_offset_s=float(d.get("end_offset_s", 0.0)),
            title_es=str(d.get("title_es", "")),
            reason=str(d.get("reason", "")),
        )

    @classmethod
    def from_json(cls, text: str) -> "ClipPick":
        # Strip markdown code fences if the LLM wrapped in ```json...```
        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(
                line for line in lines if not line.startswith("```")
            ).strip()
        return cls.from_dict(json.loads(text))


@runtime_checkable
class ClipPicker(Protocol):
    def pick(
        self,
        transcript_window: str,
        candidate: CandidateMoment,
        stream_context: str,
    ) -> ClipPick | None:
        """Evaluate one candidate moment.

        Returns ClipPick with include=True if clip-worthy, include=False to skip,
        or None if the provider failed (caller should treat as skip).
        """
        ...


# JSON schema returned by the LLM — used for validation and provider prompts.
CLIP_PICK_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "include": {
            "type": "boolean",
            "description": "true = make a clip from this moment, false = skip it",
        },
        "start_offset_s": {
            "type": "number",
            "description": "Seconds into the VOD where the clip should start",
        },
        "end_offset_s": {
            "type": "number",
            "description": "Seconds into the VOD where the clip should end (15–30 s after start)",
        },
        "title_es": {
            "type": "string",
            "description": "3–6 word Spanish title for TikTok/Shorts (catchy, no spoilers)",
        },
        "reason": {
            "type": "string",
            "description": "1–2 sentence English explanation of why this moment is (or isn't) clip-worthy",
        },
    },
    "required": ["include", "start_offset_s", "end_offset_s", "title_es", "reason"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """\
You are a clip-selection assistant for a Spanish-language Twitch streamer targeting TikTok and YouTube Shorts.

Your task: given a VOD transcript window and viewer-signal context, decide whether the highlighted moment
is genuinely clip-worthy as a standalone short video (15–30 seconds).

Respond ONLY with a valid JSON object matching this schema (no markdown, no extra text):
{
  "include": <bool>,           // true = make a clip, false = skip
  "start_offset_s": <number>,  // VOD seconds where clip starts
  "end_offset_s": <number>,    // VOD seconds where clip ends (must be 15–30 s after start)
  "title_es": <string>,        // 3–6 word Spanish title for social media
  "reason": <string>           // 1–2 sentences in English explaining your decision
}

Rules:
- Only include moments that would be entertaining or surprising as standalone clips with NO prior context.
- If the moment is mid-conversation filler, cut off, or requires setup to make sense, set include: false.
- The clip window must be 15–30 seconds. Adjust start/end relative to the candidate center.
- title_es must be in Spanish and suitable for social media captions.
- If include is false, still fill start_offset_s/end_offset_s with a best estimate and title_es with a placeholder.\
"""
