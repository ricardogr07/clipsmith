"""Tests for clipper.py."""

from __future__ import annotations

import pytest

from clipsmith.clipper import (
    _ass_time,
    _caption_lines,
    _render_ass,
    _title_slug,
    _video_filter,
)
from clipsmith.settings import CaptionConfig, ReframeConfig
from clipsmith.transcribe import Segment, Transcript, Word


# ── helpers ───────────────────────────────────────────────────────────────────

def _word(start: float, end: float, text: str) -> Word:
    return Word(start=start, end=end, word=text, probability=1.0)


def _seg(start: float, end: float, text: str, words: list[Word] | None = None) -> Segment:
    return Segment(start=start, end=end, text=text, words=words or [])


def _transcript(*segs: Segment) -> Transcript:
    return Transcript(video_id="v1", language="es", segments=list(segs))


def _cfg(**kw) -> CaptionConfig:
    defaults = {"font": "Arial", "font_size": 72, "outline": 3, "position": "bottom"}
    defaults.update(kw)
    return CaptionConfig(**defaults)


# ── _title_slug ───────────────────────────────────────────────────────────────

def test_slug_strips_accents():
    assert _title_slug("Reacción épica") == "reaccion_epica"


def test_slug_removes_punctuation():
    assert _title_slug("¡Qué bueno!") == "que_bueno"


def test_slug_lowercases():
    assert _title_slug("MOMENTO") == "momento"


def test_slug_truncates_to_40():
    assert len(_title_slug("a" * 60)) == 40


def test_slug_fallback_empty():
    assert _title_slug("!!!") == "clip"


def test_slug_spaces_become_underscores():
    assert _title_slug("hola mundo") == "hola_mundo"


# ── _ass_time ─────────────────────────────────────────────────────────────────

def test_ass_time_zero():
    assert _ass_time(0.0) == "0:00:00.00"


def test_ass_time_one_second():
    assert _ass_time(1.0) == "0:00:01.00"


def test_ass_time_half_second():
    assert _ass_time(0.5) == "0:00:00.50"


def test_ass_time_minutes():
    assert _ass_time(90.25) == "0:01:30.25"


def test_ass_time_hours():
    assert _ass_time(3661.0) == "1:01:01.00"


def test_ass_time_clamps_negative():
    assert _ass_time(-3.0) == "0:00:00.00"


# ── _caption_lines ────────────────────────────────────────────────────────────

def test_caption_lines_uses_word_timestamps():
    words = [
        _word(300.0, 300.4, "Hola"),
        _word(300.5, 300.9, "mundo"),
    ]
    t = _transcript(_seg(300.0, 301.0, "Hola mundo", words))
    lines = _caption_lines(t, 300.0, 310.0)
    assert len(lines) >= 1
    for start, end, text in lines:
        assert start >= 0.0
        assert end > start


def test_caption_lines_relative_timestamps():
    words = [_word(305.0, 305.5, "Okay")]
    t = _transcript(_seg(305.0, 305.5, "Okay", words))
    lines = _caption_lines(t, 300.0, 310.0)
    # rel_start should be ~5.0, not 305.0
    assert lines[0][0] == pytest.approx(5.0, abs=0.01)


def test_caption_lines_karaoke_tags_present():
    words = [_word(300.0, 300.5, "Hola"), _word(300.6, 301.0, "mundo")]
    t = _transcript(_seg(300.0, 301.0, "Hola mundo", words))
    lines = _caption_lines(t, 300.0, 310.0)
    combined = " ".join(text for _, _, text in lines)
    assert r"{\kf" in combined


def test_caption_lines_excludes_out_of_range():
    words = [_word(100.0, 100.5, "antes")]
    t = _transcript(_seg(100.0, 100.5, "antes", words))
    lines = _caption_lines(t, 300.0, 330.0)
    assert lines == []


def test_caption_lines_fallback_no_words():
    t = _transcript(_seg(300.0, 303.0, "Hola mundo que tal esto"))
    lines = _caption_lines(t, 300.0, 310.0)
    assert len(lines) >= 1
    for start, end, _ in lines:
        assert 0.0 <= start
        assert end <= 10.0 + 0.1


def test_caption_lines_empty_transcript():
    t = _transcript()
    assert _caption_lines(t, 300.0, 310.0) == []


def test_caption_lines_groups_long_word_runs():
    # 12 words → should produce at least 2 lines (max 5 per line)
    words = [_word(300.0 + i * 0.5, 300.3 + i * 0.5, f"w{i}") for i in range(12)]
    t = _transcript(_seg(300.0, 306.0, " ".join(w.word for w in words), words))
    lines = _caption_lines(t, 300.0, 310.0)
    assert len(lines) >= 3


# ── _render_ass ───────────────────────────────────────────────────────────────

def test_render_ass_has_sections():
    ass = _render_ass([], _cfg())
    assert "[Script Info]" in ass
    assert "[V4+ Styles]" in ass
    assert "[Events]" in ass


def test_render_ass_uses_configured_font():
    ass = _render_ass([], _cfg(font="Impact"))
    assert "Impact" in ass


def test_render_ass_bottom_alignment():
    ass = _render_ass([], _cfg(position="bottom"))
    # Alignment 2 = bottom-center in ASS numpad layout
    assert ",2," in ass


def test_render_ass_top_alignment():
    ass = _render_ass([], _cfg(position="top"))
    assert ",8," in ass


def test_render_ass_dialogue_lines():
    lines = [(0.0, 1.5, "Hola"), (2.0, 3.5, "Mundo")]
    ass = _render_ass(lines, _cfg())
    assert ass.count("Dialogue:") == 2
    assert "Hola" in ass
    assert "Mundo" in ass


def test_render_ass_playres():
    ass = _render_ass([], _cfg())
    assert "PlayResX: 1080" in ass
    assert "PlayResY: 1920" in ass


# ── _video_filter ─────────────────────────────────────────────────────────────

def test_video_filter_center(tmp_path):
    ass = tmp_path / "sub.ass"
    vf = _video_filter(ReframeConfig(mode="center"), ass)
    assert "crop=ih*9/16:ih" in vf
    assert "scale=1080:1920" in vf
    assert "subtitles=" in vf


def test_video_filter_webcam(tmp_path):
    ass = tmp_path / "sub.ass"
    reframe = ReframeConfig(mode="webcam", webcam_rect=[100, 200, 400, 711])
    vf = _video_filter(reframe, ass)
    assert "crop=400:711:100:200" in vf
    assert "scale=1080:1920" in vf


def test_video_filter_webcam_no_rect_falls_back_to_center(tmp_path):
    ass = tmp_path / "sub.ass"
    vf = _video_filter(ReframeConfig(mode="webcam", webcam_rect=None), ass)
    assert "crop=ih*9/16:ih" in vf


def test_video_filter_escapes_windows_path(tmp_path):
    ass = tmp_path / "sub.ass"
    vf = _video_filter(ReframeConfig(mode="center"), ass)
    # No raw backslashes should appear in the filter string
    assert "\\" not in vf.split("subtitles=")[1].replace("\\:", "")
