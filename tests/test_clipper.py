"""Tests for clipper.py — slug generation and video filter construction."""

from __future__ import annotations

from clipsmith.clipper import (
    _title_slug,
    _video_filter,
)
from clipsmith.settings import ReframeConfig


# ── _title_slug ───────────────────────────────────────────────────────────────

def test_slug_strips_accents() -> None:
    assert _title_slug("Reacción épica") == "reaccion_epica"


def test_slug_removes_punctuation() -> None:
    assert _title_slug("¡Qué bueno!") == "que_bueno"


def test_slug_lowercases() -> None:
    assert _title_slug("MOMENTO") == "momento"


def test_slug_truncates_to_40() -> None:
    assert len(_title_slug("a" * 60)) == 40


def test_slug_fallback_empty() -> None:
    assert _title_slug("!!!") == "clip"


def test_slug_spaces_become_underscores() -> None:
    assert _title_slug("hola mundo") == "hola_mundo"


# ── _video_filter ─────────────────────────────────────────────────────────────

def test_video_filter_center(tmp_path: object) -> None:
    from pathlib import Path
    ass = Path(str(tmp_path)) / "sub.ass"  # type: ignore[arg-type]
    vf = _video_filter(ReframeConfig(mode="center"), ass)
    assert "crop=ih*9/16:ih" in vf
    assert "scale=1080:1920" in vf
    assert "subtitles=" in vf


def test_video_filter_webcam(tmp_path: object) -> None:
    from pathlib import Path
    ass = Path(str(tmp_path)) / "sub.ass"  # type: ignore[arg-type]
    reframe = ReframeConfig(mode="webcam", webcam_rect=[100, 200, 400, 711])
    vf = _video_filter(reframe, ass)
    assert "crop=400:711:100:200" in vf
    assert "scale=1080:1920" in vf


def test_video_filter_webcam_no_rect_falls_back_to_center(tmp_path: object) -> None:
    from pathlib import Path
    ass = Path(str(tmp_path)) / "sub.ass"  # type: ignore[arg-type]
    vf = _video_filter(ReframeConfig(mode="webcam", webcam_rect=None), ass)
    assert "crop=ih*9/16:ih" in vf


def test_video_filter_escapes_windows_path(tmp_path: object) -> None:
    from pathlib import Path
    ass = Path(str(tmp_path)) / "sub.ass"  # type: ignore[arg-type]
    vf = _video_filter(ReframeConfig(mode="center"), ass)
    # No raw backslashes should appear in the filter string
    assert "\\" not in vf.split("subtitles=")[1].replace("\\:", "")
