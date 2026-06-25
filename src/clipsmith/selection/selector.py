"""Run LLM over each candidate: extract transcript window, pick, clamp duration."""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass

from ..llm.base import ClipPick, ClipPicker
from ..models.candidates import CandidateMoment
from ..models.transcript import Transcript
from ..settings import ClipConfig

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


def _spread_candidates(
    candidates: list[CandidateMoment],
    min_gap_s: float,
    max_n: int,
) -> list[CandidateMoment]:
    """Greedy time-spread: pick highest-score candidates at least min_gap_s apart.

    Iterates candidates in descending score order. A candidate is included only
    if it is at least min_gap_s seconds from every already-selected candidate.
    """
    selected: list[CandidateMoment] = []
    for c in candidates:
        if all(abs(c.t_center - s.t_center) >= min_gap_s for s in selected):
            selected.append(c)
            if len(selected) >= max_n:
                break
    return selected


def select_clips(
    candidates: list[CandidateMoment],
    transcript: Transcript,
    picker: ClipPicker,
    stream_context: str,
    config: ClipConfig,
    *,
    max_candidates: int = 20,
    min_picks: int = 2,
) -> list[PickResult]:
    """Run the LLM over the top candidates and return accepted picks.

    Only passes the top max_candidates by score to avoid excessive API calls.
    If the LLM accepts fewer than min_picks, the top-scored remaining candidates
    are force-accepted so every run produces at least some output.
    """
    top = _spread_candidates(
        sorted(candidates, key=lambda c: c.score, reverse=True),
        min_gap_s=config.min_clip_gap_s,
        max_n=max_candidates,
    )
    picks: list[PickResult] = []
    picked_centers: set[float] = set()

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
        if window.startswith("(no transcript"):
            log.warning("no transcript for t=%.1f — skipping LLM call", candidate.t_center)
            continue
        t0 = time.monotonic()
        pick = picker.pick(window, candidate, stream_context)
        elapsed_ms = round((time.monotonic() - t0) * 1000)
        if pick is None:
            log.warning("picker returned None for t=%.1f — skipping", candidate.t_center)
            continue
        log.info(
            "llm_pick",
            extra={
                "candidate_id": f"{candidate.t_center:.1f}",
                "include": pick.include,
                "score": round(candidate.score, 2),
                "elapsed_ms": elapsed_ms,
            },
        )
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
        picked_centers.add(candidate.t_center)

    # Fallback: if LLM was too strict, force-accept top candidates to meet min_picks.
    if len(picks) < min_picks and top:
        log.warning(
            "LLM accepted only %d/%d candidates — force-accepting top picks to reach min_picks=%d",
            len(picks),
            len(top),
            min_picks,
        )
        from ..llm.base import ClipPick

        for candidate in top:
            if len(picks) >= min_picks:
                break
            if candidate.t_center in picked_centers:
                continue
            if candidate.score <= 0:
                log.warning(
                    "skipping force-accept for t=%.1f: score=%.1f (zero-scored candidate)",
                    candidate.t_center,
                    candidate.score,
                )
                continue
            start_s = max(0.0, candidate.t_center - config.preroll_s)
            end_s = start_s + config.max_seconds
            forced_pick = ClipPick(
                include=True,
                start_offset_s=start_s,
                end_offset_s=end_s,
                title_es="Momento destacado",
                reason="Force-accepted: LLM accepted fewer than min_picks candidates.",
            )
            forced_pick = _clamp_duration(forced_pick, config)
            log.info(
                "  force-accepted: [%.1f-%.1f] t=%.1f score=%.1f",
                forced_pick.start_offset_s,
                forced_pick.end_offset_s,
                candidate.t_center,
                candidate.score,
            )
            picks.append(PickResult(candidate=candidate, pick=forced_pick))
            picked_centers.add(candidate.t_center)

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
        pick.end_offset_s = pick.start_offset_s + config.min_seconds
    elif duration > config.max_seconds:
        pick.end_offset_s = pick.start_offset_s + config.max_seconds
    return pick
