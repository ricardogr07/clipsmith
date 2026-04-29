"""Tests for selector.py and llm/base.py."""

from __future__ import annotations

import json

import pytest

from clipsmith.candidates import CandidateMoment
from clipsmith.llm.base import ClipPick
from clipsmith.selector import (
    _clamp_duration,
    _extract_transcript_window,
    build_stream_context,
    select_clips,
    PickResult,
)
from clipsmith.settings import ClipConfig
from clipsmith.transcribe import Segment, Transcript, Word


# ── helpers ──────────────────────────────────────────────────────────────────

def _seg(start: float, end: float, text: str) -> Segment:
    return Segment(start=start, end=end, text=text, words=[])


def _transcript(*segments: Segment) -> Transcript:
    return Transcript(video_id="v1", language="es", segments=list(segments))


def _candidate(t: float = 300.0, score: float = 50.0) -> CandidateMoment:
    return CandidateMoment(
        t_center=t,
        score=score,
        sources=["chat_density"],
        reasons=["spike at t=300"],
    )


def _cfg(**kwargs) -> ClipConfig:
    defaults = {"min_seconds": 15, "max_seconds": 30, "preroll_s": 25, "postroll_s": 10}
    defaults.update(kwargs)
    return ClipConfig(**defaults)


# ── ClipPick parsing ──────────────────────────────────────────────────────────

def test_clip_pick_from_json_plain():
    raw = json.dumps({
        "include": True,
        "start_offset_s": 290.0,
        "end_offset_s": 318.0,
        "title_es": "Reacción épica",
        "reason": "Huge chat spike, very funny moment.",
    })
    pick = ClipPick.from_json(raw)
    assert pick.include is True
    assert pick.start_offset_s == pytest.approx(290.0)
    assert pick.end_offset_s == pytest.approx(318.0)
    assert pick.title_es == "Reacción épica"


def test_clip_pick_from_json_strips_markdown_fences():
    raw = "```json\n{\"include\":false,\"start_offset_s\":0,\"end_offset_s\":0,\"title_es\":\"n/a\",\"reason\":\"not funny\"}\n```"
    pick = ClipPick.from_json(raw)
    assert pick.include is False


def test_clip_pick_duration():
    pick = ClipPick(include=True, start_offset_s=100.0, end_offset_s=125.0, title_es="t", reason="r")
    assert pick.duration_s == pytest.approx(25.0)


def test_clip_pick_roundtrip():
    original = ClipPick(include=True, start_offset_s=50.0, end_offset_s=78.5, title_es="Momento", reason="good")
    restored = ClipPick.from_dict(original.to_dict())
    assert restored.include == original.include
    assert restored.start_offset_s == pytest.approx(original.start_offset_s)
    assert restored.title_es == original.title_es


# ── duration clamping ─────────────────────────────────────────────────────────

def test_clamp_too_short_extends_end():
    pick = ClipPick(include=True, start_offset_s=100.0, end_offset_s=109.0, title_es="t", reason="r")
    clamped = _clamp_duration(pick, _cfg(min_seconds=15, max_seconds=30))
    assert clamped.end_offset_s == pytest.approx(115.0)


def test_clamp_too_long_trims_end():
    pick = ClipPick(include=True, start_offset_s=100.0, end_offset_s=145.0, title_es="t", reason="r")
    clamped = _clamp_duration(pick, _cfg(min_seconds=15, max_seconds=30))
    assert clamped.end_offset_s == pytest.approx(130.0)


def test_clamp_ok_unchanged():
    pick = ClipPick(include=True, start_offset_s=100.0, end_offset_s=120.0, title_es="t", reason="r")
    clamped = _clamp_duration(pick, _cfg(min_seconds=15, max_seconds=30))
    assert clamped.end_offset_s == pytest.approx(120.0)


# ── transcript window extraction ──────────────────────────────────────────────

def test_extract_window_includes_segments_in_range():
    t = _transcript(
        _seg(0.0, 5.0, "intro"),
        _seg(240.0, 245.0, "before window"),
        _seg(260.0, 265.0, "in window"),
        _seg(300.0, 305.0, "center"),
        _seg(325.0, 330.0, "after center"),
        _seg(500.0, 505.0, "far future"),
    )
    window = _extract_transcript_window(t, t_center=300.0)
    assert "in window" in window
    assert "center" in window
    assert "after center" in window
    assert "intro" not in window
    assert "far future" not in window


def test_extract_window_empty_transcript():
    t = _transcript()
    window = _extract_transcript_window(t, t_center=100.0)
    assert "no transcript" in window.lower()


def test_extract_window_has_relative_timestamps():
    t = _transcript(_seg(300.0, 302.0, "right at center"))
    window = _extract_transcript_window(t, t_center=300.0)
    assert "+0.0s" in window or "+0" in window


# ── select_clips with mock picker ─────────────────────────────────────────────

class _AcceptAll:
    """Mock picker that accepts every candidate."""
    def __init__(self):
        self.calls: list[CandidateMoment] = []

    def pick(self, transcript_window, candidate, stream_context) -> ClipPick:
        self.calls.append(candidate)
        return ClipPick(
            include=True,
            start_offset_s=candidate.t_center - 10,
            end_offset_s=candidate.t_center + 15,
            title_es="Momento gracioso",
            reason="Mock: accepted.",
        )


class _RejectAll:
    """Mock picker that rejects every candidate."""
    def pick(self, transcript_window, candidate, stream_context) -> ClipPick:
        return ClipPick(
            include=False,
            start_offset_s=0.0,
            end_offset_s=0.0,
            title_es="n/a",
            reason="Mock: rejected.",
        )


class _FailAll:
    """Mock picker that always errors."""
    def pick(self, transcript_window, candidate, stream_context) -> None:
        return None


def _make_transcript_with_content() -> Transcript:
    return _transcript(
        _seg(100.0, 105.0, " Muy gracioso"),
        _seg(290.0, 295.0, " Primer candidato"),
        _seg(490.0, 495.0, " Segundo candidato"),
    )


def test_select_clips_accept_all():
    candidates = [_candidate(300.0, 80.0), _candidate(500.0, 60.0)]
    transcript = _make_transcript_with_content()
    picker = _AcceptAll()
    picks = select_clips(candidates, transcript, picker, "ctx", _cfg(), max_candidates=10)
    assert len(picks) == 2
    assert len(picker.calls) == 2


def test_select_clips_reject_all():
    candidates = [_candidate(300.0)]
    picks = select_clips(candidates, _make_transcript_with_content(), _RejectAll(), "ctx", _cfg())
    assert picks == []


def test_select_clips_fail_treated_as_skip():
    candidates = [_candidate(300.0)]
    picks = select_clips(candidates, _make_transcript_with_content(), _FailAll(), "ctx", _cfg())
    assert picks == []


def test_select_clips_respects_max_candidates():
    candidates = [_candidate(float(i * 100), float(100 - i)) for i in range(10)]
    picker = _AcceptAll()
    select_clips(candidates, _make_transcript_with_content(), picker, "ctx", _cfg(), max_candidates=3)
    assert len(picker.calls) == 3


def test_select_clips_clamped_duration():
    """The picker returns a 60s clip; select_clips should clamp it to 30s."""
    class _LongPick:
        def pick(self, tw, c, sc) -> ClipPick:
            return ClipPick(
                include=True,
                start_offset_s=c.t_center - 5,
                end_offset_s=c.t_center + 55,  # 60s — too long
                title_es="Largo",
                reason="test",
            )
    candidates = [_candidate(300.0)]
    picks = select_clips(
        candidates, _make_transcript_with_content(), _LongPick(), "ctx", _cfg(max_seconds=30)
    )
    assert len(picks) == 1
    assert picks[0].pick.duration_s == pytest.approx(30.0)


def test_build_stream_context_contains_channel():
    ctx = build_stream_context("chuyelwuero", "Stream title", "3h21m4s")
    assert "chuyelwuero" in ctx
    assert "Spanish" in ctx
    assert "3h21m4s" in ctx
