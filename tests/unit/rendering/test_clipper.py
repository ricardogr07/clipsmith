"""Tests for rendering.clipper — slug generation and video filter construction."""

from __future__ import annotations

from pathlib import Path

from clipsmith.rendering.clipper import (
    _build_ffmpeg_cmd,
    _stacked_filter_complex,
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
    ass = Path(str(tmp_path)) / "sub.ass"  # type: ignore[arg-type]
    vf = _video_filter(ReframeConfig(mode="center"), ass)
    assert "crop=ih*9/16:ih" in vf
    assert "scale=1080:1920" in vf
    assert "subtitles=" in vf


def test_video_filter_webcam(tmp_path: object) -> None:
    ass = Path(str(tmp_path)) / "sub.ass"  # type: ignore[arg-type]
    reframe = ReframeConfig(mode="webcam", webcam_rect=[100, 200, 400, 711])
    vf = _video_filter(reframe, ass)
    assert "crop=400:711:100:200" in vf
    assert "scale=1080:1920" in vf


def test_video_filter_webcam_no_rect_falls_back_to_center(tmp_path: object) -> None:
    ass = Path(str(tmp_path)) / "sub.ass"  # type: ignore[arg-type]
    vf = _video_filter(ReframeConfig(mode="webcam", webcam_rect=None), ass)
    assert "crop=ih*9/16:ih" in vf


def test_video_filter_escapes_windows_path(tmp_path: object) -> None:
    ass = Path(str(tmp_path)) / "sub.ass"  # type: ignore[arg-type]
    vf = _video_filter(ReframeConfig(mode="center"), ass)
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


# ── _stacked_filter_complex ───────────────────────────────────────────────────


def _stacked_cfg(**kw) -> ReframeConfig:
    return ReframeConfig(mode="stacked", **kw)


def test_stacked_filter_both_rects() -> None:
    cfg = _stacked_cfg(webcam_rect=[100, 50, 400, 300], gameplay_rect=[0, 0, 1920, 1080])
    fc = _stacked_filter_complex(cfg, None)
    assert "crop=400:300:100:50" in fc
    assert "crop=1920:1080:0:0" in fc
    assert "vstack" in fc
    assert "[out]" in fc


def test_stacked_filter_no_webcam_rect_falls_back_to_center_top() -> None:
    cfg = _stacked_cfg(webcam_rect=None, gameplay_rect=[0, 0, 1920, 1080])
    fc = _stacked_filter_complex(cfg, None)
    chains = fc.split(";")
    assert "crop=ih*9/16:ih" in chains[0]


def test_stacked_filter_no_gameplay_rect_falls_back_to_center_bot() -> None:
    cfg = _stacked_cfg(webcam_rect=[0, 0, 400, 300], gameplay_rect=None)
    fc = _stacked_filter_complex(cfg, None)
    chains = fc.split(";")
    assert "crop=ih*9/16:ih" in chains[1]


def test_stacked_filter_split_ratio_pixel_heights() -> None:
    cfg = _stacked_cfg(split_ratio=0.4)
    fc = _stacked_filter_complex(cfg, None)
    assert "scale=1080:768" in fc  # int(1920 * 0.4) = 768
    assert "scale=1080:1152" in fc  # 1920 - 768 = 1152


def test_stacked_filter_captions_after_vstack(tmp_path: Path) -> None:
    ass = tmp_path / "sub.ass"
    cfg = _stacked_cfg()
    fc = _stacked_filter_complex(cfg, ass)
    last_chain = fc.split(";")[-1]
    assert "vstack" in last_chain
    assert "subtitles=" in last_chain


def test_stacked_filter_no_captions() -> None:
    cfg = _stacked_cfg()
    fc = _stacked_filter_complex(cfg, None)
    assert "subtitles=" not in fc
    assert "[out]" in fc


def test_ffmpeg_cmd_stacked_uses_filter_complex(tmp_path: Path) -> None:
    mp4 = tmp_path / "v.mp4"
    out = tmp_path / "clip.mp4"
    cmd = _build_ffmpeg_cmd(mp4, 10.0, 40.0, None, _stacked_cfg(), out)
    assert "-filter_complex" in cmd
    assert "-vf" not in cmd
    assert "libx264" in cmd


def test_ffmpeg_cmd_stacked_maps_audio(tmp_path: Path) -> None:
    mp4 = tmp_path / "v.mp4"
    out = tmp_path / "clip.mp4"
    cmd = _build_ffmpeg_cmd(mp4, 10.0, 40.0, None, _stacked_cfg(), out)
    assert "0:a" in cmd
    assert cmd.count("-map") >= 2
