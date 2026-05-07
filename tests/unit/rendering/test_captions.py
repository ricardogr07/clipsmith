"""Tests for rendering.captions — ASS subtitle generation."""

from __future__ import annotations

import pytest

from helpers import _seg, _transcript, _word
from clipsmith.rendering.captions import (
    _ass_time,
    _caption_lines,
    _render_ass,
)
from clipsmith.settings import CaptionConfig


def _cfg(**kw: object) -> CaptionConfig:
    defaults: dict[str, object] = {
        "font": "Arial",
        "font_size": 72,
        "outline": 3,
        "position": "bottom",
    }
    defaults.update(kw)
    return CaptionConfig(**defaults)  # type: ignore[arg-type]


# ── _ass_time ─────────────────────────────────────────────────────────────────


def test_ass_time_zero() -> None:
    assert _ass_time(0.0) == "0:00:00.00"


def test_ass_time_one_second() -> None:
    assert _ass_time(1.0) == "0:00:01.00"


def test_ass_time_half_second() -> None:
    assert _ass_time(0.5) == "0:00:00.50"


def test_ass_time_minutes() -> None:
    assert _ass_time(90.25) == "0:01:30.25"


def test_ass_time_hours() -> None:
    assert _ass_time(3661.0) == "1:01:01.00"


def test_ass_time_clamps_negative() -> None:
    assert _ass_time(-3.0) == "0:00:00.00"


# ── _caption_lines ────────────────────────────────────────────────────────────


def test_caption_lines_uses_word_timestamps() -> None:
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


def test_caption_lines_relative_timestamps() -> None:
    words = [_word(305.0, 305.5, "Okay")]
    t = _transcript(_seg(305.0, 305.5, "Okay", words))
    lines = _caption_lines(t, 300.0, 310.0)
    assert lines[0][0] == pytest.approx(5.0, abs=0.01)


def test_caption_lines_karaoke_tags_present() -> None:
    words = [_word(300.0, 300.5, "Hola"), _word(300.6, 301.0, "mundo")]
    t = _transcript(_seg(300.0, 301.0, "Hola mundo", words))
    lines = _caption_lines(t, 300.0, 310.0)
    combined = " ".join(text for _, _, text in lines)
    assert r"{\kf" in combined


def test_caption_lines_excludes_out_of_range() -> None:
    words = [_word(100.0, 100.5, "antes")]
    t = _transcript(_seg(100.0, 100.5, "antes", words))
    lines = _caption_lines(t, 300.0, 330.0)
    assert lines == []


def test_caption_lines_fallback_no_words() -> None:
    t = _transcript(_seg(300.0, 303.0, "Hola mundo que tal esto"))
    lines = _caption_lines(t, 300.0, 310.0)
    assert len(lines) >= 1
    for start, end, _ in lines:
        assert 0.0 <= start
        assert end <= 10.0 + 0.1


def test_caption_lines_empty_transcript() -> None:
    t = _transcript()
    assert _caption_lines(t, 300.0, 310.0) == []


def test_caption_lines_groups_long_word_runs() -> None:
    words = [_word(300.0 + i * 0.5, 300.3 + i * 0.5, f"w{i}") for i in range(12)]
    t = _transcript(_seg(300.0, 306.0, " ".join(w.word for w in words), words))
    lines = _caption_lines(t, 300.0, 310.0)
    assert len(lines) >= 3


# ── _render_ass ───────────────────────────────────────────────────────────────


def test_render_ass_has_sections() -> None:
    ass = _render_ass([], _cfg())
    assert "[Script Info]" in ass
    assert "[V4+ Styles]" in ass
    assert "[Events]" in ass


def test_render_ass_uses_configured_font() -> None:
    ass = _render_ass([], _cfg(font="Impact"))
    assert "Impact" in ass


def test_render_ass_bottom_alignment() -> None:
    ass = _render_ass([], _cfg(position="bottom"))
    assert ",2," in ass


def test_render_ass_top_alignment() -> None:
    ass = _render_ass([], _cfg(position="top"))
    assert ",8," in ass


def test_render_ass_dialogue_lines() -> None:
    lines = [(0.0, 1.5, "Hola"), (2.0, 3.5, "Mundo")]
    ass = _render_ass(lines, _cfg())
    assert ass.count("Dialogue:") == 2
    assert "Hola" in ass
    assert "Mundo" in ass


def test_render_ass_playres() -> None:
    ass = _render_ass([], _cfg())
    assert "PlayResX: 1080" in ass
    assert "PlayResY: 1920" in ass
