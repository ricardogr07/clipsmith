"""Audio RMS energy extraction and peak detection via ffmpeg astats filter."""

from __future__ import annotations

import json
import logging
import re
import subprocess  # nosec B403
from pathlib import Path

log = logging.getLogger(__name__)


def compute_audio_rms_series(
    mp4: Path,
    window_s: float = 2.0,
    *,
    cache_dir: Path | None = None,
) -> list[tuple[float, float]]:
    """Return (t_center, rms_db) per analysis window. Skips silence (db <= -90).

    Results are cached to <cache_dir>/audio_rms.json so the expensive ffmpeg
    scan only runs once per VOD. Pass cache_dir=None to disable caching.
    Uses ffmpeg astats + ametadata filters — no Python audio library required.
    """
    cache_path = (cache_dir / "audio_rms.json") if cache_dir is not None else None

    if cache_path is not None and cache_path.exists():
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        points: list[tuple[float, float]] = [tuple(p) for p in data]  # type: ignore[misc]
        log.info(
            "audio RMS series: loaded %d windows from cache (%s)", len(points), cache_path.name
        )
        return points

    sample_rate = 16000
    reset_samples = int(window_s * sample_rate)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(mp4),
        "-af",
        f"aresample={sample_rate},"
        f"astats=metadata=1:reset={reset_samples},"
        "ametadata=mode=print:file=-",
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)  # nosec B603 — cmd built from internal config and mp4 path only
    points = []
    for m in re.finditer(
        r"pts_time:(\S+).*?lavfi\.astats\.Overall\.RMS_level=(\S+)",
        result.stdout,
        re.DOTALL,
    ):
        try:
            t = float(m.group(1)) + window_s / 2
            db = float(m.group(2))
            if db > -90:
                points.append((t, db))
        except ValueError:
            continue
    log.info("audio RMS series: %d windows from %s", len(points), mp4.name)

    if cache_path is not None:
        cache_path.write_text(json.dumps(points), encoding="utf-8")
        log.info("audio RMS series cached to %s", cache_path.name)

    return points


def find_rms_peaks(
    series: list[tuple[float, float]],
    peak_multiplier: float = 2.0,
) -> list[tuple[float, float]]:
    """Return (t_center, norm_score) for windows at least peak_multiplier σ above mean.

    norm_score = (rms_db - mean) / std — louder spikes score proportionally higher.
    Returns [] for empty or essentially flat (std < 0.5 dB) series.
    """
    if len(series) < 2:
        return []
    dbs = [db for _, db in series]
    mean = sum(dbs) / len(dbs)
    std = (sum((d - mean) ** 2 for d in dbs) / len(dbs)) ** 0.5
    if std < 0.5:
        return []
    threshold = mean + peak_multiplier * std
    return [(t, (db - mean) / std) for t, db in series if db >= threshold]
