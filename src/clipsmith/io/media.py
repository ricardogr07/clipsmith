"""Shared media-file utilities (ffprobe/ffmpeg helpers used across modules)."""

from __future__ import annotations

import subprocess  # nosec B403
from pathlib import Path


def video_duration(mp4: Path) -> float:
    """Return video duration in seconds via ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(mp4),
    ]
    out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()  # nosec B603
    return float(out)
