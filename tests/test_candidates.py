"""Tests for candidates.py and candidates_math.py."""

from __future__ import annotations

import pytest

from clipsmith.candidates import build_candidates, _dedupe
from clipsmith.candidates_math import compute_density_scores
from clipsmith.chat import ChatLog, ChatMessage
from clipsmith.settings import CandidatesConfig
from clipsmith.twitch_client import Clip


# ── helpers ──────────────────────────────────────────────────────────────────

def _msg(t: float, text: str = "hey", author: str = "user", hype: int = 0) -> ChatMessage:
    return ChatMessage(
        time_in_seconds=t,
        message=text,
        author=author,
        is_clip_command=text.strip().lower().startswith("!clip"),
        hype_emote_count=hype,
    )


def _chat(messages: list[ChatMessage]) -> ChatLog:
    return ChatLog(video_id="v1", messages=messages)


def _clip(offset: int, clip_id: str = "c1", views: int = 100) -> Clip:
    return Clip(
        id=clip_id,
        url="https://twitch.tv/clip/x",
        title="funny moment",
        creator_name="creator",
        video_id="v1",
        vod_offset=offset,
        duration=25.0,
        view_count=views,
        created_at="2026-04-27T20:30:00Z",
    )


def _cfg(**overrides) -> CandidatesConfig:
    return CandidatesConfig(**overrides)


# ── density math ──────────────────────────────────────────────────────────────

def test_density_detects_spike():
    # 50 quiet messages spread across 500s, then a burst of 40 in 15s window.
    quiet = [_msg(float(i * 10)) for i in range(50)]
    burst_center = 300.0
    burst = [_msg(burst_center + i * 0.3) for i in range(40)]
    msgs = quiet + burst

    scores = compute_density_scores(msgs, window_s=15, peak_multiplier=4.0, step_s=5.0)
    assert scores, "expected at least one density peak"
    peak_times = [t for t, _ in scores]
    # Peak should land near 300s
    assert any(290 <= t <= 320 for t in peak_times), f"peak not near burst: {peak_times}"


def test_density_empty_chat():
    assert compute_density_scores([], window_s=15, peak_multiplier=4.0) == []


def test_density_hype_emotes_boost_score():
    # Two windows with same message count; one has hype emotes — should score higher.
    base = [_msg(float(i)) for i in range(100)]
    plain_burst = [_msg(200.0 + i * 0.2) for i in range(20)]
    hyped_burst = [_msg(400.0 + i * 0.2, hype=2) for i in range(20)]

    plain_scores = compute_density_scores(base + plain_burst, window_s=15, peak_multiplier=2.0)
    hyped_scores = compute_density_scores(base + hyped_burst, window_s=15, peak_multiplier=2.0)

    plain_max = max((s for _, s in plain_scores), default=0)
    hyped_max = max((s for _, s in hyped_scores), default=0)
    assert hyped_max > plain_max


# ── deduplication ────────────────────────────────────────────────────────────

def test_dedupe_merges_close_events():
    raw = [
        (100.0, 10.0, "chat_density", "spike at 100"),
        (110.0, 20.0, "clip_command", "!clip at 110"),
        (115.0, 5.0,  "chat_density", "spike at 115"),
        (300.0, 15.0, "existing_clip", "clip at 300"),
    ]
    result = _dedupe(raw, window_s=60)
    assert len(result) == 2
    times = {c.t_center for c in result}
    # 100, 110, 115 all within 60s of the first — merged into one (centered on 110 as highest score)
    assert any(abs(t - 110.0) < 1 for t in times)
    assert any(abs(t - 300.0) < 1 for t in times)


def test_dedupe_accumulates_scores():
    raw = [
        (50.0, 10.0, "chat_density", "a"),
        (55.0, 20.0, "clip_command", "b"),
    ]
    result = _dedupe(raw, window_s=60)
    assert len(result) == 1
    assert result[0].score == pytest.approx(30.0)
    assert set(result[0].sources) == {"chat_density", "clip_command"}


def test_dedupe_preserves_distinct_events():
    raw = [(float(i * 100), 5.0, "chat_density", f"t={i*100}") for i in range(5)]
    result = _dedupe(raw, window_s=60)
    assert len(result) == 5


# ── build_candidates integration ─────────────────────────────────────────────

def test_existing_clip_gets_boost():
    cfg = _cfg(existing_clip_boost=100.0, clip_command_boost=25.0, density_peak_multiplier=99.0)
    chat = _chat([_msg(float(i * 5)) for i in range(20)])  # sparse, no density peaks
    clips = [_clip(offset=300, clip_id="c1", views=500)]

    candidates = build_candidates(chat, clips, cfg)
    assert candidates, "expected at least one candidate"
    top = candidates[0]
    assert top.t_center == pytest.approx(300.0)
    assert "existing_clip" in top.sources
    assert top.score >= 100.0


def test_clip_command_creates_candidate():
    cfg = _cfg(density_peak_multiplier=99.0, clip_command_boost=25.0)
    msgs = [_msg(float(i * 10)) for i in range(30)]
    msgs.append(_msg(150.0, "!clip this", "viewer1"))
    chat = _chat(msgs)

    candidates = build_candidates(chat, [], cfg)
    clip_cmd_candidates = [c for c in candidates if "clip_command" in c.sources]
    assert clip_cmd_candidates, "!clip should create a candidate"
    assert any(abs(c.t_center - 150.0) < 1 for c in clip_cmd_candidates)


def test_candidates_sorted_by_score_descending():
    cfg = _cfg(existing_clip_boost=100.0, clip_command_boost=25.0, density_peak_multiplier=99.0)
    msgs = [_msg(float(i * 10)) for i in range(30)]
    msgs.append(_msg(100.0, "!clip", "a"))
    msgs.append(_msg(200.0, "!clip", "b"))
    chat = _chat(msgs)
    clips = [_clip(offset=200, clip_id="c1")]  # overlap with !clip at 200 — merged, big score

    candidates = build_candidates(chat, clips, cfg)
    scores = [c.score for c in candidates]
    assert scores == sorted(scores, reverse=True)


def test_no_candidates_for_completely_empty_data():
    cfg = _cfg()
    candidates = build_candidates(_chat([]), [], cfg)
    assert candidates == []


# ── transcript hype signal ────────────────────────────────────────────────────

def _transcript(segments: list[tuple[float, float, str]]):
    from clipsmith.transcribe import Segment, Transcript, Word
    segs = [Segment(start=s, end=e, text=t, words=[]) for s, e, t in segments]
    return Transcript(video_id="v1", language="es", segments=segs)


def test_transcript_hype_keyword_creates_candidate():
    cfg = _cfg(density_peak_multiplier=99.0)
    tr = _transcript([(120.0, 123.0, " jajaja qué bueno!")])
    candidates = build_candidates(_chat([]), [], cfg, transcript=tr)
    hype = [c for c in candidates if "transcript_hype" in c.sources]
    assert hype, "hype keyword should create a candidate"
    assert any(abs(c.t_center - 121.5) < 2 for c in hype)


def test_transcript_hype_exclamation_scores():
    cfg = _cfg(transcript_hype_score=12.0)
    tr = _transcript([(50.0, 52.0, "¡increíble!")])
    candidates = build_candidates(_chat([]), [], cfg, transcript=tr)
    hype = [c for c in candidates if "transcript_hype" in c.sources]
    assert hype
    assert hype[0].score > 0


def test_transcript_no_hype_no_candidate():
    cfg = _cfg(density_peak_multiplier=99.0)
    tr = _transcript([(10.0, 12.0, "bien jugado"), (20.0, 22.0, "seguimos")])
    candidates = build_candidates(_chat([]), [], cfg, transcript=tr)
    hype = [c for c in candidates if "transcript_hype" in c.sources]
    assert not hype


def test_transcript_hype_merges_with_clip_command():
    cfg = _cfg(clip_command_boost=25.0, transcript_hype_score=12.0, density_peak_multiplier=99.0)
    msgs = [_msg(100.0, "!clip")]
    tr = _transcript([(101.0, 103.0, "jajaja wow")])  # within 60s dedupe window
    candidates = build_candidates(_chat(msgs), [], cfg, transcript=tr)
    merged = [c for c in candidates if "clip_command" in c.sources and "transcript_hype" in c.sources]
    assert merged, "clip_command and nearby transcript_hype should merge"
    assert merged[0].score > 25.0  # combined score
