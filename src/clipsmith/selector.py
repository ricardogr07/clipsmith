"""Run LLM over each candidate: extract transcript window, pick, clamp duration."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from .candidates import CandidateMoment
from .llm.base import ClipPick, ClipPicker
from .settings import ClipConfig
from .transcribe import Transcript

log = logging.getLogger(__name__)

# Seconds of transcript to send before/after the candidate center.
WINDOW_PRE_S = 60.0
WINDOW_POST_S = 30.0


@dataclass
class PickResult:
    candidate: CandidateMoment
    pick: ClipPick

    def to_dict(self) -> dict:
        return {
            "candidate": asdict(self.candidate),
            "pick": self.pick.to_dict(),
        }


def select_clips(
    candidates: list[CandidateMoment],
    transcript: Transcript,
    picker: ClipPicker,
    stream_context: str,
    config: ClipConfig,
    *,
    max_candidates: int = 20,
) -> list[PickResult]:
    """Run the LLM over the top candidates and return accepted picks.

    Only passes the top max_candidates by score to avoid excessive API calls.
    """
    top = sorted(candidates, key=lambda c: c.score, reverse=True)[:max_candidates]
    picks: list[PickResult] = []

    for i, candidate in enumerate(top, 1):
        log.info(
            "LLM candidate %d/%d  t=%.1f  score=%.1f  signals=%s",
            i,
            len(top),
            candidate.t_center,
            candidate.score,
            candidate.sources,
        )
        window = _extract_transcript_window(transcript, candidate.t_center)
        pick = picker.pick(window, candidate, stream_context)
        if pick is None:
            log.warning("picker returned None for t=%.1f — skipping", candidate.t_center)
            continue
        if not pick.include:
            log.debug("LLM rejected t=%.1f: %s", candidate.t_center, pick.reason)
            continue

        pick = _clamp_duration(pick, config)
        log.info(
            "  accepted: [%.1f-%.1f] (%.1fs) - %s",
            pick.start_offset_s,
            pick.end_offset_s,
            pick.duration_s,
            pick.title_es.encode("ascii", "replace").decode("ascii"),
        )
        picks.append(PickResult(candidate=candidate, pick=pick))

    return picks


def _extract_transcript_window(transcript: Transcript, t_center: float) -> str:
    """Return a formatted string of transcript lines within the window."""
    t_start = max(0.0, t_center - WINDOW_PRE_S)
    t_end = t_center + WINDOW_POST_S

    lines: list[str] = []
    for seg in transcript.segments:
        if seg.end < t_start or seg.start > t_end:
            continue
        rel = seg.start - t_center
        sign = "+" if rel >= 0 else ""
        lines.append(f"[{sign}{rel:+.1f}s] {seg.text.strip()}")

    if not lines:
        return "(no transcript available for this window)"
    return "\n".join(lines)


def _clamp_duration(pick: ClipPick, config: ClipConfig) -> ClipPick:
    """Ensure the clip is within [min_seconds, max_seconds]."""
    duration = pick.end_offset_s - pick.start_offset_s
    if duration < config.min_seconds:
        # Extend end until minimum is met.
        pick.end_offset_s = pick.start_offset_s + config.min_seconds
    elif duration > config.max_seconds:
        # Trim end to maximum.
        pick.end_offset_s = pick.start_offset_s + config.max_seconds
    return pick


def build_stream_context(channel: str, vod_title: str, vod_duration: str) -> str:
    return (
        f"Stream context:\n"
        f"Channel: {channel}\n"
        f"VOD title: {vod_title}\n"
        f"Duration: {vod_duration}\n"
        f"Language: Spanish\n"
        f"Platform: Twitch (clips for TikTok/YouTube Shorts)\n"
    )


def save_picks(picks: list[PickResult], path: Path) -> None:
    path.write_text(
        json.dumps([p.to_dict() for p in picks], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
