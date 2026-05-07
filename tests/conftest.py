"""Shared test helpers for clipsmith tests."""

from __future__ import annotations

from clipsmith.models.transcript import Segment, Transcript, Word


def _word(start: float, end: float, text: str) -> Word:
    return Word(start=start, end=end, word=text, probability=1.0)


def _seg(start: float, end: float, text: str, words: list[Word] | None = None) -> Segment:
    return Segment(start=start, end=end, text=text, words=words or [])


def _transcript(*segments: Segment) -> Transcript:
    return Transcript(video_id="v1", language="es", segments=list(segments))
