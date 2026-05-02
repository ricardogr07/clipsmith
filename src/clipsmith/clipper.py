"""Clip cutter: ffmpeg trim → 9:16 reframe → burned ASS captions."""

from __future__ import annotations

import logging
import re
import subprocess
import unicodedata
from pathlib import Path

from .captions import _write_ass
from .selector import PickResult
from .settings import AppConfig, ReframeConfig
from .transcribe import Transcript

log = logging.getLogger(__name__)


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

    ass_path = out_path.with_suffix(".ass")
    _write_ass(transcript, start, end, config.caption, ass_path)

    cmd = _build_ffmpeg_cmd(mp4_path, start, end, ass_path, config.reframe, out_path)
    log.info("clip %d  [%.1f-%.1fs]  ->  %s", index, start, end, out_path.name)
    log.debug("ffmpeg: %s", " ".join(cmd))

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error("ffmpeg stderr:\n%s", result.stderr[-2000:])
        raise RuntimeError(f"ffmpeg failed for clip {index} ({out_path.name})")
    return out_path


def _build_ffmpeg_cmd(
    mp4_path: Path,
    start: float,
    end: float,
    ass_path: Path,
    reframe: ReframeConfig,
    out_path: Path,
) -> list[str]:
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start:.3f}",
        "-i", str(mp4_path),
        "-t", f"{end - start:.3f}",
    ]
    if reframe.mode == "none":
        cmd += ["-c:v", "copy", "-c:a", "copy"]
    else:
        cmd += [
            "-vf", _video_filter(reframe, ass_path),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
        ]
    cmd += ["-movflags", "+faststart", str(out_path)]
    return cmd


def _video_filter(reframe: ReframeConfig, ass_path: Path) -> str:
    if reframe.mode == "webcam" and reframe.webcam_rect:
        x, y, w, h = reframe.webcam_rect
        crop = f"crop={w}:{h}:{x}:{y},scale=1080:1920:flags=lanczos"
    else:
        crop = "crop=ih*9/16:ih,scale=1080:1920:flags=lanczos"

    # ffmpeg filter paths: forward slashes, drive colon escaped
    ass_str = str(ass_path).replace("\\", "/").replace(":", "\\:")
    return f"{crop},subtitles='{ass_str}'"


def _title_slug(title: str) -> str:
    """Filesystem-safe ASCII slug from a Spanish clip title."""
    # Decompose accented chars (é → e + combining accent), then drop combiners
    normalized = unicodedata.normalize("NFKD", title)
    ascii_only = "".join(c for c in normalized if not unicodedata.combining(c))
    slug = ascii_only.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "_", slug)
    return slug.strip("_-")[:40] or "clip"
