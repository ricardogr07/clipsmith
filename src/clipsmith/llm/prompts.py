"""LLM prompt templates and candidate-message builders.

All prompt text lives here so providers never import from each other.
"""

from __future__ import annotations

from ..models.candidates import CandidateMoment

SYSTEM_PROMPT = """\
You are a clip-selection assistant for a Spanish-language Twitch streamer targeting TikTok and YouTube Shorts.

Your task: given a VOD transcript window and viewer-signal context, decide whether the highlighted moment
is genuinely clip-worthy as a standalone short video (~150 seconds / 2 min 30 sec).

Respond ONLY with a valid JSON object matching this schema (no markdown, no extra text):
{
  "include": <bool>,           // true = make a clip, false = skip
  "start_offset_s": <number>,  // VOD seconds where clip starts
  "end_offset_s": <number>,    // VOD seconds where clip ends (must be ~150 s after start)
  "title_es": <string>,        // 3–6 word Spanish title for social media
  "reason": <string>           // 1–2 sentences in English explaining your decision
}

Rules:
- Only include moments that would be entertaining or surprising as standalone clips with NO prior context.
- If the moment is mid-conversation filler, cut off, or requires setup to make sense, set include: false.
- The clip window must be ~150 seconds. Adjust start/end relative to the candidate center.
- title_es must be in Spanish and suitable for social media captions.
- If include is false, still fill start_offset_s/end_offset_s with a best estimate and title_es with a placeholder.\
"""

SYSTEM_PROMPT_V2 = """\
You are a clip-selection assistant for a Spanish-language Twitch streamer making TikTok/YouTube Shorts.

Given a VOD moment with viewer signals and transcript, decide if it works as a standalone ~150 s clip (2 min 30 sec).

Reply ONLY with valid JSON (no markdown):
{"include":<bool>,"start_offset_s":<n>,"end_offset_s":<n>,"title_es":<str 3-6 words>,"reason":<str 1 sentence>}

Include ONLY moments with: clear momentum, emotional peak, or punchline that lands without setup.
Skip: mid-story filler, off-camera reactions, anything needing prior context.\
"""


def get_system_prompt(version: str = "v1") -> str:
    """Return the system prompt for the given version string."""
    return SYSTEM_PROMPT_V2 if version == "v2" else SYSTEM_PROMPT


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
            "description": "Seconds into the VOD where the clip should end (~150 s after start)",
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


def build_candidate_prompt(transcript_window: str, candidate: CandidateMoment) -> str:
    """Build the per-candidate user message sent to any LLM provider."""
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


def build_stream_context(channel: str, vod_title: str, vod_duration: str) -> str:
    """Build the stable per-VOD context block sent before candidate prompts."""
    return (
        f"Stream context:\n"
        f"Channel: {channel}\n"
        f"VOD title: {vod_title}\n"
        f"Duration: {vod_duration}\n"
        f"Language: Spanish\n"
        f"Platform: Twitch (clips for TikTok/YouTube Shorts)\n"
    )
