"""Transcript domain models: Word, Segment, Transcript."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Self


@dataclass
class Word:
    start: float  # seconds
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
    def from_json(cls: type[Self], text: str) -> Self:
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
