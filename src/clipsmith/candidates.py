"""Combine signals into a ranked list of CandidateMoments.

Signals:
  1. Existing Twitch clips for this VOD (vod_offset as hard candidate, score boost).
  2. Chat !clip commands (viewer-driven marker).
  3. Chat density peaks + hype-emote weighting (sliding window).
  4. Transcript hype keywords / exclamations in speech.
  5. Audio RMS energy spikes (streamer raises voice).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .candidates_math import compute_density_scores
from .chat import ChatLog
from .settings import CandidatesConfig
from .transcribe import Transcript
from .twitch_client import Clip

# Spanish/stream hype keywords that suggest a funny or exciting moment.
_HYPE_KEYWORDS = frozenset(
    {
        "jaja",
        "jeje",
        "jajaj",
        "jajaja",
        "lmao",
        "lol",
        "xd",
        "xdd",
        "omg",
        "wow",
        "nooo",
        "noooo",
        "increíble",
        "increible",
        "tremendo",
        "brutal",
        "dios",
        "wtf",
        "carajo",
        "caray",
        "bestia",
        "monstro",
    }
)


@dataclass
class CandidateMoment:
    t_center: float  # seconds into VOD
    score: float
    sources: list[str]  # human-readable signal labels
    reasons: list[str]  # detail strings for the LLM prompt

    def to_dict(self) -> dict:
        return asdict(self)


def build_candidates(
    chat: ChatLog,
    existing_clips: list[Clip],
    config: CandidatesConfig,
    *,
    transcript: Transcript | None = None,
    vod_duration_s: float | None = None,
    mp4_path: Path | None = None,
) -> list[CandidateMoment]:
    """Return CandidateMoments sorted by score descending."""
    raw: list[tuple[float, float, str, str]] = []  # (t, score, source, reason)

    # --- Signal 1: existing Twitch clips ---
    for clip in existing_clips:
        if clip.vod_offset is None:
            continue
        raw.append(
            (
                float(clip.vod_offset),
                config.existing_clip_boost,
                "existing_clip",
                f"Twitch clip {clip.id!r} ({clip.view_count} views): {clip.title!r}",
            )
        )

    # --- Signal 2: !clip chat commands ---
    for msg in chat.messages:
        if msg.is_clip_command:
            raw.append(
                (
                    msg.time_in_seconds,
                    config.clip_command_boost,
                    "clip_command",
                    f"!clip by {msg.author} at t={msg.time_in_seconds:.1f}s",
                )
            )

    # --- Signal 3: chat density peaks ---
    density_scores = compute_density_scores(
        chat.messages,
        window_s=config.density_window_s,
        peak_multiplier=config.density_peak_multiplier,
    )
    for t, score in density_scores:
        raw.append(
            (
                t,
                score,
                "chat_density",
                f"chat density peak (score={score:.1f}) at t={t:.1f}s",
            )
        )

    # --- Signal 4: transcript hype moments (laughter/exclamations in speech) ---
    if transcript is not None:
        for seg in transcript.segments:
            text = seg.text.lower()
            kw_hits = sum(1 for kw in _HYPE_KEYWORDS if kw in text)
            punct_hits = text.count("!") + text.count("¡")
            score = kw_hits * config.transcript_hype_score + punct_hits * (
                config.transcript_hype_score / 3
            )
            if score > 0:
                t = (seg.start + seg.end) / 2
                raw.append(
                    (
                        t,
                        score,
                        "transcript_hype",
                        f"hype in transcript at t={seg.start:.1f}s: {seg.text.strip()!r}",
                    )
                )

    # --- Signal 5: audio RMS energy spikes (raised voice) ---
    if config.audio_energy_enabled and mp4_path is not None:
        from .audio_signal import compute_audio_rms_series, find_rms_peaks

        series = compute_audio_rms_series(
            mp4_path, config.audio_energy_window_s, cache_dir=mp4_path.parent
        )
        for t, norm_score in find_rms_peaks(series, config.audio_energy_peak_multiplier):
            raw.append(
                (
                    t,
                    norm_score * config.audio_energy_boost,
                    "audio_energy",
                    f"voice spike at {t:.1f}s ({norm_score:.1f}σ above baseline)",
                )
            )

    # --- Merge: deduplicate within dedupe_window_s, keeping max score ---
    merged = _dedupe(raw, window_s=config.dedupe_window_s)
    merged = _normalize_scores(merged)

    return sorted(merged, key=lambda c: c.score, reverse=True)


def _dedupe(
    raw: list[tuple[float, float, str, str]],
    window_s: float,
) -> list[CandidateMoment]:
    """Collapse events within window_s of each other, accumulating scores and labels."""
    if not raw:
        return []

    # Sort by time so we can sweep once.
    events = sorted(raw, key=lambda x: x[0])
    groups: list[list[tuple[float, float, str, str]]] = []
    current: list[tuple[float, float, str, str]] = [events[0]]

    for ev in events[1:]:
        if ev[0] - current[0][0] <= window_s:
            current.append(ev)
        else:
            groups.append(current)
            current = [ev]
    groups.append(current)

    candidates: list[CandidateMoment] = []
    for group in groups:
        # Center on the highest-score event in the group.
        best = max(group, key=lambda x: x[1])
        total_score = sum(x[1] for x in group)
        sources = list(dict.fromkeys(x[2] for x in group))  # unique, ordered
        reasons = list(dict.fromkeys(x[3] for x in group))  # unique, ordered
        candidates.append(
            CandidateMoment(
                t_center=best[0],
                score=total_score,
                sources=sources,
                reasons=reasons,
            )
        )
    return candidates


def _normalize_scores(candidates: list[CandidateMoment]) -> list[CandidateMoment]:
    """Map raw scores to [1, 100] preserving rank order."""
    if len(candidates) < 2:
        for c in candidates:
            c.score = 50.0
        return candidates
    lo = min(c.score for c in candidates)
    hi = max(c.score for c in candidates)
    if hi == lo:
        for c in candidates:
            c.score = 50.0
        return candidates
    for c in candidates:
        c.score = round(1.0 + 99.0 * (c.score - lo) / (hi - lo), 1)
    return candidates


def save_candidates(candidates: list[CandidateMoment], path: Path) -> None:
    path.write_text(
        json.dumps([c.to_dict() for c in candidates], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_candidates(path: Path) -> list[CandidateMoment]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [CandidateMoment(**d) for d in data]
