"""Unit tests for models.transcript — serialization roundtrip."""

from __future__ import annotations

import json

from clipsmith.models.transcript import Segment, Transcript, Word


def _make_transcript(video_id: str = "v1") -> Transcript:
    return Transcript(
        video_id=video_id,
        language="es",
        segments=[
            Segment(
                start=0.0,
                end=2.5,
                text=" Hola amigos",
                words=[
                    Word(start=0.1, end=0.5, word=" Hola", probability=0.99),
                    Word(start=0.6, end=1.0, word=" amigos", probability=0.97),
                ],
            ),
            Segment(
                start=2.5,
                end=5.0,
                text=" bienvenidos al stream",
                words=[
                    Word(start=2.6, end=3.0, word=" bienvenidos", probability=0.95),
                    Word(start=3.1, end=3.4, word=" al", probability=0.98),
                    Word(start=3.5, end=4.0, word=" stream", probability=0.96),
                ],
            ),
        ],
    )


def test_roundtrip_json() -> None:
    t = _make_transcript()
    restored = Transcript.from_json(t.to_json())
    assert restored.video_id == t.video_id
    assert restored.language == t.language
    assert len(restored.segments) == 2
    assert restored.segments[0].text == " Hola amigos"
    assert restored.segments[0].words[0].word == " Hola"
    assert restored.segments[1].words[2].word == " stream"


def test_to_json_is_valid_json() -> None:
    t = _make_transcript()
    data = json.loads(t.to_json())
    assert data["video_id"] == "v1"
    assert data["language"] == "es"
    assert len(data["segments"]) == 2


def test_from_json_empty_words() -> None:
    raw = json.dumps(
        {
            "video_id": "v2",
            "language": "es",
            "segments": [
                {"start": 0.0, "end": 1.0, "text": "foo", "words": []},
            ],
        }
    )
    t = Transcript.from_json(raw)
    assert t.segments[0].words == []
