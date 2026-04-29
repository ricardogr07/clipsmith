"""Transcription via faster-whisper: Spanish audio, word timestamps."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from .settings import TranscribeConfig

log = logging.getLogger(__name__)


@dataclass
class Word:
    start: float   # seconds
    end: float
    word: str
    probability: float


@dataclass
class Segment:
    start: float
    end: float
    text: str
    words: list[Word]


@dataclass
class Transcript:
    video_id: str
    language: str
    segments: list[Segment]

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, text: str) -> "Transcript":
        d = json.loads(text)
        d["segments"] = [
            Segment(
                start=s["start"],
                end=s["end"],
                text=s["text"],
                words=[Word(**w) for w in s.get("words", [])],
            )
            for s in d["segments"]
        ]
        return cls(**d)


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
    """
    if out_path is None:
        out_path = mp4_path.parent / "transcript.json"

    if out_path.exists() and not overwrite:
        log.info("loading cached transcript: %s", out_path)
        return Transcript.from_json(out_path.read_text(encoding="utf-8"))

    # Import here so the package is importable even without faster-whisper installed.
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
