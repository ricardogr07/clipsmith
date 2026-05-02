"""Subprocess wrapper around `twitch-dl download`."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class DownloadResult:
    video_id: str
    mp4_path: Path


def download_vod(
    video_id: str,
    work_dir: Path,
    *,
    quality: str = "best",
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

    cmd = [
        "python", "-m", "twitchdl", "download", video_id,
        "--quality", quality,
        "--output", str(out_path),
    ]
    if overwrite:
        cmd.append("--overwrite")

    log.info("running: %s", " ".join(cmd))
    subprocess.run(cmd, check=True, text=True, capture_output=False)
    log.info("download finished: %s", out_path)
    return DownloadResult(video_id=video_id, mp4_path=out_path)
