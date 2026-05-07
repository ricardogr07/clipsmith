"""Transcription via faster-whisper: Spanish audio, word timestamps."""

from __future__ import annotations

import logging
import subprocess  # nosec B403
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .io.media import video_duration
from .models.transcript import Segment, Transcript, Word
from .settings import TranscribeConfig

log = logging.getLogger(__name__)

# Re-export models so existing imports from this module keep working
# during the transition; downstream code should prefer models.transcript.
__all__ = ["Word", "Segment", "Transcript", "transcribe"]


def _extract_audio_chunk(mp4: Path, start_s: float, duration_s: float, out_wav: Path) -> None:
    """Extract a mono 16kHz WAV slice from mp4 using ffmpeg."""
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(start_s),
        "-t",
        str(duration_s),
        "-i",
        str(mp4),
        "-vn",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(out_wav),
    ]
    subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # nosec B603


def _transcribe_chunk(
    model: Any,
    wav_path: Path,
    offset_s: float,
    config: TranscribeConfig,
) -> list[Segment]:
    """Transcribe one audio chunk and adjust timestamps by offset_s."""
    raw_segments, _ = model.transcribe(
        str(wav_path),
        language=config.language,
        word_timestamps=True,
        beam_size=5,
        vad_filter=True,
    )
    segments: list[Segment] = []
    for seg in raw_segments:
        words = [
            Word(
                start=w.start + offset_s,
                end=w.end + offset_s,
                word=w.word,
                probability=w.probability,
            )
            for w in (seg.words or [])
        ]
        segments.append(
            Segment(
                start=seg.start + offset_s,
                end=seg.end + offset_s,
                text=seg.text,
                words=words,
            )
        )
    return segments


def _merge_segments(
    chunks: list[list[Segment]],
    chunk_starts: list[float],
) -> list[Segment]:
    """Merge chunk segment lists, dropping overlap duplicates.

    For chunk N+1, any segment whose start falls before chunk_starts[N+1] is in the
    overlap zone that chunk N already covered — drop it to avoid duplicate text.
    """
    merged: list[Segment] = []
    for i, segs in enumerate(chunks):
        cutoff = chunk_starts[i]
        for seg in segs:
            if seg.start >= cutoff:
                merged.append(seg)
    merged.sort(key=lambda s: s.start)
    return merged


def _chunked_transcribe(
    mp4: Path,
    video_id: str,
    config: TranscribeConfig,
    out_path: Path,
) -> Transcript:
    """Split audio into chunks, transcribe in parallel, merge results."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise ImportError(
            "faster-whisper is required for transcription: pip install faster-whisper"
        ) from exc

    duration = video_duration(mp4)
    chunk_s = config.chunk_minutes * 60
    overlap_s = config.chunk_overlap_s

    chunk_starts: list[float] = []
    slices: list[tuple[float, float]] = []
    t = 0.0
    while t < duration:
        extract_dur = min(chunk_s + overlap_s, duration - t)
        chunk_starts.append(t)
        slices.append((t, extract_dur))
        t += chunk_s

    n = len(slices)
    log.info(
        "chunked transcription: %d chunks of %dmin (+%ds overlap), workers=%d",
        n,
        config.chunk_minutes,
        overlap_s,
        config.max_workers,
    )

    log.info(
        "loading faster-whisper model=%s compute_type=%s",
        config.model,
        config.compute_type,
    )
    model = WhisperModel(config.model, device="cpu", compute_type=config.compute_type)

    with tempfile.TemporaryDirectory() as tmp:
        wav_paths: list[Path] = []
        for idx, (start, dur) in enumerate(slices):
            wav = Path(tmp) / f"chunk_{idx:03d}.wav"
            log.info("extracting chunk %d/%d (t=%.0fs, dur=%.0fs)...", idx + 1, n, start, dur)
            _extract_audio_chunk(mp4, start, dur, wav)
            wav_paths.append(wav)

        chunk_results: list[list[Segment]] = [[] for _ in range(n)]
        with ThreadPoolExecutor(max_workers=config.max_workers) as pool:
            future_to_idx = {
                pool.submit(_transcribe_chunk, model, wav_paths[i], chunk_starts[i], config): i
                for i in range(n)
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                chunk_results[idx] = future.result()
                log.info("chunk %d/%d transcribed (%d segs)", idx + 1, n, len(chunk_results[idx]))

    segments = _merge_segments(chunk_results, chunk_starts)
    language = config.language
    transcript = Transcript(video_id=video_id, language=language, segments=segments)
    out_path.write_text(transcript.to_json(), encoding="utf-8")
    log.info("transcript saved: %s (%d segments, %d chunks)", out_path, len(segments), n)
    return transcript


def transcribe(
    mp4_path: Path,
    video_id: str,
    config: TranscribeConfig,
    *,
    out_path: Path | None = None,
    overwrite: bool = False,
) -> Transcript:
    """Transcribe audio from mp4_path using faster-whisper.

    Saves transcript.json next to the mp4 (or to out_path).
    On second call, loads from disk unless overwrite=True.
    If config.chunk_minutes > 0, uses parallel chunked transcription.
    """
    if out_path is None:
        out_path = mp4_path.parent / "transcript.json"

    if out_path.exists() and not overwrite:
        log.info("loading cached transcript: %s", out_path)
        return Transcript.from_json(out_path.read_text(encoding="utf-8"))

    if config.chunk_minutes > 0:
        return _chunked_transcribe(mp4_path, video_id, config, out_path)

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise ImportError(
            "faster-whisper is required for transcription: pip install faster-whisper"
        ) from exc

    log.info(
        "loading faster-whisper model=%s compute_type=%s",
        config.model,
        config.compute_type,
    )
    model = WhisperModel(config.model, device="cpu", compute_type=config.compute_type)

    log.info("transcribing %s (language=%s) ...", mp4_path.name, config.language)
    raw_segments, info = model.transcribe(
        str(mp4_path),
        language=config.language,
        word_timestamps=True,
        beam_size=5,
        vad_filter=True,
    )

    segments: list[Segment] = []
    for seg in raw_segments:
        words = [
            Word(
                start=w.start,
                end=w.end,
                word=w.word,
                probability=w.probability,
            )
            for w in (seg.words or [])
        ]
        segments.append(Segment(start=seg.start, end=seg.end, text=seg.text, words=words))
        log.debug("[%.1f -> %.1f] %s", seg.start, seg.end, seg.text.strip())

    transcript = Transcript(
        video_id=video_id,
        language=info.language,
        segments=segments,
    )
    out_path.write_text(transcript.to_json(), encoding="utf-8")
    log.info("transcript saved: %s (%d segments)", out_path, len(segments))
    return transcript
