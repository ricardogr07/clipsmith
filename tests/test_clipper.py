"""Tests for clipper.py — slug generation and video filter construction."""

from __future__ import annotations
from pathlib import Path

from clipsmith.clipper import (
    _build_ffmpeg_cmd,
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


def test_video_filter_no_captions_center() -> None:
    vf = _video_filter(ReframeConfig(mode="center"), None)
    assert "crop=ih*9/16:ih" in vf
    assert "subtitles=" not in vf


def test_video_filter_captions_no_reframe(tmp_path: Path) -> None:
    ass = tmp_path / "sub.ass"
    vf = _video_filter(ReframeConfig(mode="none"), ass)
    assert "subtitles=" in vf
    assert "crop=" not in vf


def test_video_filter_none_mode_no_captions() -> None:
    vf = _video_filter(ReframeConfig(mode="none"), None)
    assert vf == ""


# ── _build_ffmpeg_cmd ─────────────────────────────────────────────────────────

def test_ffmpeg_cmd_stream_copy_when_no_reframe_no_captions(tmp_path: Path) -> None:
    mp4 = tmp_path / "v.mp4"
    out = tmp_path / "clip.mp4"
    cmd = _build_ffmpeg_cmd(mp4, 10.0, 40.0, None, ReframeConfig(mode="none"), out)
    assert "-c:v" in cmd
    assert "copy" in cmd
    assert "libx264" not in cmd


def test_ffmpeg_cmd_reencode_when_reframe_enabled(tmp_path: Path) -> None:
    mp4 = tmp_path / "v.mp4"
    out = tmp_path / "clip.mp4"
    cmd = _build_ffmpeg_cmd(mp4, 10.0, 40.0, None, ReframeConfig(mode="center"), out)
    assert "libx264" in cmd
    assert "-vf" in cmd


def test_ffmpeg_cmd_reencode_when_captions_enabled(tmp_path: Path) -> None:
    mp4 = tmp_path / "v.mp4"
    ass = tmp_path / "sub.ass"
    out = tmp_path / "clip.mp4"
    cmd = _build_ffmpeg_cmd(mp4, 10.0, 40.0, ass, ReframeConfig(mode="none"), out)
    assert "libx264" in cmd
    assert "-vf" in cmd
