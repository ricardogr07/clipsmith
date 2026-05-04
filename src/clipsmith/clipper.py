"""Clip cutter: ffmpeg trim → 9:16 reframe → burned ASS captions."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess  # nosec B403
import sys
import unicodedata
from pathlib import Path

from .captions import _write_ass
from .selector import PickResult
from .settings import AppConfig, ReframeConfig
from .transcribe import Transcript

log = logging.getLogger(__name__)


def _find_ffmpeg() -> str:
    """Return path to ffmpeg: bundled copy next to exe, or fall back to PATH."""
    bundled = Path(sys.executable).parent / "ffmpeg.exe"
    if bundled.exists():
        return str(bundled)
    path = shutil.which("ffmpeg")
    if path is None:
        raise RuntimeError("ffmpeg not found on PATH")
    return path


def cut_all_clips(
    mp4_path: Path,
    transcript: Transcript,
    picks: list[PickResult],
    out_dir: Path,
    config: AppConfig,
) -> list[Path]:
    """Cut, reframe, and caption every accepted pick. Returns paths of created files."""
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[Path] = []
    for i, pr in enumerate(picks, 1):
        slug = _title_slug(pr.pick.title_es)
        out_path = out_dir / f"clip_{i:02d}_{slug}.mp4"
        results.append(_cut_one(mp4_path, transcript, pr, i, out_path, config))
    return results


def _cut_one(
    mp4_path: Path,
    transcript: Transcript,
    pr: PickResult,
    index: int,
    out_path: Path,
    config: AppConfig,
) -> Path:
    start = pr.pick.start_offset_s
    end = pr.pick.end_offset_s

    ass_path: Path | None = None
    if config.caption.enabled:
        ass_path = out_path.with_suffix(".ass")
        _write_ass(transcript, start, end, config.caption, ass_path)

    cmd = _build_ffmpeg_cmd(mp4_path, start, end, ass_path, config.reframe, out_path)
    log.info("clip %d  [%.1f-%.1fs]  ->  %s", index, start, end, out_path.name)
    log.debug("ffmpeg: %s", " ".join(cmd))

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)  # nosec B603 — cmd built internally by _build_ffmpeg_cmd
    except FileNotFoundError:
        raise RuntimeError(
            "ffmpeg not found. Place ffmpeg.exe next to clipsmith.exe or add it to PATH."
        )
    if result.returncode != 0:
        log.error("ffmpeg stderr:\n%s", result.stderr[-2000:])
        raise RuntimeError(f"ffmpeg failed for clip {index} ({out_path.name})")
    return out_path


def _build_ffmpeg_cmd(
    mp4_path: Path,
    start: float,
    end: float,
    ass_path: Path | None,
    reframe: ReframeConfig,
    out_path: Path,
) -> list[str]:
    cmd = [
        _find_ffmpeg(),
        "-y",
        "-ss",
        f"{start:.3f}",
        "-i",
        str(mp4_path),
        "-t",
        f"{end - start:.3f}",
    ]
    if reframe.mode == "none" and ass_path is None:
        cmd += ["-c:v", "copy", "-c:a", "copy"]
    elif reframe.mode == "stacked":
        cmd += _stacked_encode_args(reframe, ass_path)
    else:
        vf = _video_filter(reframe, ass_path)
        cmd += [
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
        ]
    cmd += ["-movflags", "+faststart", str(out_path)]
    return cmd


def _video_filter(reframe: ReframeConfig, ass_path: Path | None) -> str:
    parts: list[str] = []

    if reframe.mode == "webcam" and reframe.webcam_rect:
        x, y, w, h = reframe.webcam_rect
        parts.append(f"crop={w}:{h}:{x}:{y},scale=1080:1920:flags=lanczos")
    elif reframe.mode != "none":
        parts.append("crop=ih*9/16:ih,scale=1080:1920:flags=lanczos")

    if ass_path is not None:
        # ffmpeg filter paths: forward slashes, drive colon escaped
        ass_str = str(ass_path).replace("\\", "/").replace(":", "\\:")
        parts.append(f"subtitles='{ass_str}'")

    return ",".join(parts)


def _stacked_filter_complex(reframe: ReframeConfig, ass_path: Path | None) -> str:
    top_h = int(1920 * reframe.split_ratio)
    bot_h = 1920 - top_h

    if reframe.webcam_rect:
        x, y, w, h = reframe.webcam_rect
        top = f"[0:v]crop={w}:{h}:{x}:{y},scale=1080:{top_h}:flags=lanczos[top]"
    else:
        log.warning("reframe.webcam_rect not set — using center-crop for top panel")
        top = f"[0:v]crop=ih*9/16:ih,scale=1080:{top_h}:flags=lanczos[top]"

    if reframe.gameplay_rect:
        x, y, w, h = reframe.gameplay_rect
        bot = f"[0:v]crop={w}:{h}:{x}:{y},scale=1080:{bot_h}:flags=lanczos[bot]"
    else:
        bot = f"[0:v]crop=ih*9/16:ih,scale=1080:{bot_h}:flags=lanczos[bot]"

    if ass_path is not None:
        ass_str = str(ass_path).replace("\\", "/").replace(":", "\\:")
        stack = f"[top][bot]vstack,subtitles='{ass_str}'[out]"
    else:
        stack = "[top][bot]vstack[out]"

    return ";".join([top, bot, stack])


def _stacked_encode_args(reframe: ReframeConfig, ass_path: Path | None) -> list[str]:
    fc = _stacked_filter_complex(reframe, ass_path)
    return [
        "-filter_complex",
        fc,
        "-map",
        "[out]",
        "-map",
        "0:a",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
    ]


def _title_slug(title: str) -> str:
    """Filesystem-safe ASCII slug from a Spanish clip title."""
    # Decompose accented chars (é → e + combining accent), then drop combiners
    normalized = unicodedata.normalize("NFKD", title)
    ascii_only = "".join(c for c in normalized if not unicodedata.combining(c))
    slug = ascii_only.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "_", slug)
    return slug.strip("_-")[:40] or "clip"
