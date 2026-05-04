"""Subprocess wrapper around `twitch-dl download`."""

from __future__ import annotations

import logging
import subprocess  # nosec B403
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class DownloadResult:
    video_id: str
    mp4_path: Path


_QUALITY_PREFERENCE = ["1080p60", "720p60", "480p", "360p", "160p"]


def _resolve_quality(video_id: str, preferred: str) -> str:
    """Return the best available quality, falling back through the preference list."""
    result = subprocess.run(  # nosec B603 — invoking twitchdl module; video_id is a numeric string from Twitch API
        ["python", "-m", "twitchdl", "info", video_id],
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    if preferred in output:
        return preferred
    for q in _QUALITY_PREFERENCE:
        if q in output:
            log.info("quality '%s' not available, using '%s'", preferred, q)
            return q
    return preferred  # let twitchdl report the error with context


def download_vod(
    video_id: str,
    work_dir: Path,
    *,
    quality: str = "1080p60",
    overwrite: bool = False,
) -> DownloadResult:
    """Download a Twitch VOD using twitch-dl.

    Returns the path to the downloaded MP4.
    Raises subprocess.CalledProcessError on failure.
    """
    vod_dir = work_dir / video_id
    vod_dir.mkdir(parents=True, exist_ok=True)
    out_path = vod_dir / f"{video_id}.mp4"

    if out_path.exists() and not overwrite:
        log.info("VOD %s already downloaded: %s", video_id, out_path)
        return DownloadResult(video_id=video_id, mp4_path=out_path)

    resolved = _resolve_quality(video_id, quality)
    cmd = [
        "python",
        "-m",
        "twitchdl",
        "download",
        video_id,
        "--quality",
        resolved,
        "--output",
        str(out_path),
    ]
    if overwrite:
        cmd.append("--overwrite")

    log.info("running: %s", " ".join(cmd))
    subprocess.run(cmd, check=True, text=True, capture_output=False)  # nosec B603 — cmd built from internal config values and Twitch video_id
    log.info("download finished: %s", out_path)
    return DownloadResult(video_id=video_id, mp4_path=out_path)
