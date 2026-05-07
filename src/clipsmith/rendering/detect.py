"""Webcam/face rectangle detection from a source VOD via OpenCV Haar cascades."""

from __future__ import annotations

import json
import logging
import subprocess  # nosec B403
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from ..io.media import video_duration

if TYPE_CHECKING:
    from ..settings import ReframeConfig

log = logging.getLogger(__name__)

_WEBCAM_RECT_CACHE = "webcam_rect.json"

_SAMPLE_COUNT = 20
_MIN_HIT_RATE = 0.3
_IOU_MERGE = 0.3


def _extract_frame(mp4: Path, t: float, out_png: Path) -> bool:
    """Extract one frame at timestamp t into out_png. Returns True on success."""
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(t),
        "-i",
        str(mp4),
        "-vframes",
        "1",
        "-q:v",
        "2",
        str(out_png),
    ]
    result = subprocess.run(cmd, capture_output=True)  # nosec B603 — cmd contains only internal paths and ffmpeg flags
    return result.returncode == 0 and out_png.exists()


def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(ax, bx)
    iy = max(ay, by)
    ix2 = min(ax + aw, bx + bw)
    iy2 = min(ay + ah, by + bh)
    inter = max(0, ix2 - ix) * max(0, iy2 - iy)
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def _cluster_rects(
    rects: list[tuple[int, int, int, int]],
) -> list[tuple[tuple[int, int, int, int], int]]:
    """Group overlapping rects by IOU. Returns list of (representative_rect, count) sorted by count descending."""
    clusters: list[list[tuple[int, int, int, int]]] = []
    for r in rects:
        merged = False
        for cluster in clusters:
            if _iou(cluster[0], r) >= _IOU_MERGE:
                cluster.append(r)
                merged = True
                break
        if not merged:
            clusters.append([r])

    result = []
    for cluster in clusters:
        xs = [r[0] for r in cluster]
        ys = [r[1] for r in cluster]
        ws = [r[2] for r in cluster]
        hs = [r[3] for r in cluster]
        rep = (
            int(sum(xs) / len(xs)),
            int(sum(ys) / len(ys)),
            int(sum(ws) / len(ws)),
            int(sum(hs) / len(hs)),
        )
        result.append((rep, len(cluster)))

    result.sort(key=lambda x: x[1], reverse=True)
    return result


def detect_webcam_rect(
    mp4: Path,
    sample_count: int = _SAMPLE_COUNT,
    scale_factor: float = 1.1,
    min_neighbors: int = 5,
    min_face_frac: float = 0.03,
    max_face_frac: float = 0.35,
) -> list[int] | None:
    """Sample frames from *mp4*, detect faces via Haar cascade, cluster results,
    and return the most-consistent [x, y, w, h] rect in source-video pixels.

    Returns None if no stable face is found.
    """
    try:
        import cv2  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError(
            "opencv-python-headless is required for webcam detection. "
            "Run: pip install opencv-python-headless"
        ) from exc

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"  # type: ignore[attr-defined]
    cascade = cv2.CascadeClassifier(cascade_path)
    if cascade.empty():
        raise RuntimeError(f"Failed to load Haar cascade from {cascade_path}")

    duration = video_duration(mp4)
    if duration <= 0:
        raise RuntimeError(f"Could not determine duration of {mp4}")

    margin = duration * 0.05
    step = (duration - 2 * margin) / (sample_count - 1)
    timestamps = [margin + i * step for i in range(sample_count)]

    all_rects: list[tuple[int, int, int, int]] = []
    hits = 0

    with tempfile.TemporaryDirectory() as tmp:
        for i, t in enumerate(timestamps):
            png = Path(tmp) / f"frame_{i:03d}.png"
            if not _extract_frame(mp4, t, png):
                log.debug("frame extraction failed at t=%.1fs", t)
                continue

            frame = cv2.imread(str(png))
            if frame is None:
                continue

            h_frame, w_frame = frame.shape[:2]
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            short_side = min(w_frame, h_frame)
            min_px = int(short_side * min_face_frac)
            max_px = int(short_side * max_face_frac)

            faces = cascade.detectMultiScale(
                gray,
                scaleFactor=scale_factor,
                minNeighbors=min_neighbors,
                minSize=(min_px, min_px),
                maxSize=(max_px, max_px),
            )

            if len(faces) > 0:
                hits += 1
                for x, y, w, h in faces:
                    all_rects.append((int(x), int(y), int(w), int(h)))

            log.debug(
                "t=%.1fs  faces=%d  total_rects=%d",
                t,
                len(faces) if len(faces) > 0 else 0,
                len(all_rects),
            )

    if not all_rects:
        log.warning("No faces detected in any sampled frame")
        return None

    hit_rate = hits / sample_count
    log.info("Face detected in %d/%d frames (%.0f%%)", hits, sample_count, hit_rate * 100)

    if hit_rate < _MIN_HIT_RATE:
        log.warning(
            "Face hit rate %.0f%% below threshold %.0f%% — result may be unreliable",
            hit_rate * 100,
            _MIN_HIT_RATE * 100,
        )

    clusters = _cluster_rects(all_rects)
    best_rect, best_count = clusters[0]

    log.info(
        "Best cluster: rect=%s  hits=%d/%d  (%.0f%%)",
        list(best_rect),
        best_count,
        len(all_rects),
        best_count / len(all_rects) * 100,
    )

    if len(clusters) > 1:
        log.info(
            "Other candidate clusters: %s",
            [(list(r), c) for r, c in clusters[1:3]],
        )

    return list(best_rect)


def load_or_detect_webcam_rect(mp4: Path, vod_dir: Path, reframe: "ReframeConfig") -> None:
    """Populate reframe.webcam_rect if not already set.

    Order of precedence:
      1. Already set in config — do nothing.
      2. Cache file work/<video_id>/webcam_rect.json exists — load it.
      3. Run detection, cache result, update reframe in-place.
    """
    if reframe.mode == "none":
        return
    if reframe.webcam_rect:
        return

    cache = vod_dir / _WEBCAM_RECT_CACHE
    if cache.exists():
        reframe.webcam_rect = json.loads(cache.read_text(encoding="utf-8"))
        log.info("webcam rect loaded from cache: %s", reframe.webcam_rect)
        return

    log.info("webcam_rect not set — running face detection on %s ...", mp4.name)
    try:
        rect = detect_webcam_rect(mp4)
    except RuntimeError as exc:
        log.warning("webcam detection skipped (%s); set webcam_rect in config.yaml manually", exc)
        return

    if rect is None:
        log.warning("no stable face detected; set webcam_rect manually in config.yaml")
        return

    cache.write_text(json.dumps(rect), encoding="utf-8")
    reframe.webcam_rect = rect
    log.info("webcam rect detected and cached to %s: %s", cache, rect)
