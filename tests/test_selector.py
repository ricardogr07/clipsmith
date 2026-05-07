"""Tests for selector.py — transcript windowing and clip selection logic."""

from __future__ import annotations

from conftest import _seg, _transcript

import pytest

from clipsmith.models.candidates import CandidateMoment
from clipsmith.llm.base import ClipPick
from clipsmith.llm.prompts import build_stream_context
from clipsmith.selection.selector import (
    _extract_transcript_window,
    select_clips,
)
from clipsmith.settings import ClipConfig


def _candidate(t: float = 300.0, score: float = 50.0) -> CandidateMoment:
    return CandidateMoment(
        t_center=t,
        score=score,
        sources=["chat_density"],
        reasons=["spike at t=300"],
    )


def _cfg(**kwargs: object) -> ClipConfig:
    defaults: dict[str, object] = {
        "min_seconds": 15,
        "max_seconds": 30,
        "preroll_s": 25,
        "postroll_s": 10,
    }
    defaults.update(kwargs)
    return ClipConfig(**defaults)  # type: ignore[arg-type]


# ── transcript window extraction ──────────────────────────────────────────────


def test_extract_window_includes_segments_in_range() -> None:
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


def test_extract_window_empty_transcript() -> None:
    t = _transcript()
    window = _extract_transcript_window(t, t_center=100.0)
    assert "no transcript" in window.lower()


def test_extract_window_has_relative_timestamps() -> None:
    t = _transcript(_seg(300.0, 302.0, "right at center"))
    window = _extract_transcript_window(t, t_center=300.0)
    assert "+0.0s" in window or "+0" in window


# ── select_clips with mock picker ─────────────────────────────────────────────


class _AcceptAll:
    """Mock picker that accepts every candidate."""

    def __init__(self) -> None:
        self.calls: list[CandidateMoment] = []

    def pick(
        self, transcript_window: str, candidate: CandidateMoment, stream_context: str
    ) -> ClipPick:
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

    def pick(
        self, transcript_window: str, candidate: CandidateMoment, stream_context: str
    ) -> ClipPick:
        return ClipPick(
            include=False,
            start_offset_s=0.0,
            end_offset_s=0.0,
            title_es="n/a",
            reason="Mock: rejected.",
        )


class _FailAll:
    """Mock picker that always errors."""

    def pick(self, transcript_window: str, candidate: CandidateMoment, stream_context: str) -> None:
        return None


def _make_transcript_with_content() -> object:
    return _transcript(
        _seg(100.0, 105.0, " Muy gracioso"),
        _seg(290.0, 295.0, " Primer candidato"),
        _seg(490.0, 495.0, " Segundo candidato"),
    )


def test_select_clips_accept_all() -> None:
    candidates = [_candidate(300.0, 80.0), _candidate(500.0, 60.0)]
    transcript = _make_transcript_with_content()
    picker = _AcceptAll()
    picks = select_clips(candidates, transcript, picker, "ctx", _cfg(), max_candidates=10)  # type: ignore[arg-type]
    assert len(picks) == 2
    assert len(picker.calls) == 2


def test_select_clips_reject_all() -> None:
    candidates = [_candidate(300.0)]
    picks = select_clips(candidates, _make_transcript_with_content(), _RejectAll(), "ctx", _cfg())  # type: ignore[arg-type]
    assert picks == []


def test_select_clips_fail_treated_as_skip() -> None:
    candidates = [_candidate(300.0)]
    picks = select_clips(candidates, _make_transcript_with_content(), _FailAll(), "ctx", _cfg())  # type: ignore[arg-type]
    assert picks == []


def test_select_clips_respects_max_candidates() -> None:
    candidates = [_candidate(float(i * 100), float(100 - i)) for i in range(10)]
    picker = _AcceptAll()
    select_clips(
        candidates, _make_transcript_with_content(), picker, "ctx", _cfg(), max_candidates=3
    )  # type: ignore[arg-type]
    assert len(picker.calls) == 3


def test_select_clips_clamped_duration() -> None:
    """The picker returns a 60s clip; select_clips should clamp it to 30s."""

    class _LongPick:
        def pick(self, tw: str, c: CandidateMoment, sc: str) -> ClipPick:
            return ClipPick(
                include=True,
                start_offset_s=c.t_center - 5,
                end_offset_s=c.t_center + 55,  # 60s — too long
                title_es="Largo",
                reason="test",
            )

    candidates = [_candidate(300.0)]
    picks = select_clips(
        candidates,
        _make_transcript_with_content(),
        _LongPick(),
        "ctx",
        _cfg(max_seconds=30),  # type: ignore[arg-type]
    )
    assert len(picks) == 1
    assert picks[0].pick.duration_s == pytest.approx(30.0)


def test_build_stream_context_contains_channel() -> None:
    ctx = build_stream_context("chuyelwuero", "Stream title", "3h21m4s")
    assert "chuyelwuero" in ctx
    assert "Spanish" in ctx
    assert "3h21m4s" in ctx
