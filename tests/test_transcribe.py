"""Tests for transcribe.py — no real audio needed."""

from __future__ import annotations

import json
from unittest.mock import patch

from clipsmith.transcribe import Segment, Transcript, Word, _merge_segments, _extract_audio_chunk


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


def test_roundtrip_json():
    t = _make_transcript()
    restored = Transcript.from_json(t.to_json())
    assert restored.video_id == t.video_id
    assert restored.language == t.language
    assert len(restored.segments) == 2
    assert restored.segments[0].text == " Hola amigos"
    assert restored.segments[0].words[0].word == " Hola"
    assert restored.segments[1].words[2].word == " stream"


def test_to_json_is_valid_json():
    t = _make_transcript()
    data = json.loads(t.to_json())
    assert data["video_id"] == "v1"
    assert data["language"] == "es"
    assert len(data["segments"]) == 2


def test_from_json_empty_words():
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


def test_transcribe_loads_from_cache(tmp_path):
    """transcribe() should return cached transcript.json without importing faster-whisper."""
    from clipsmith.transcribe import transcribe
    from clipsmith.settings import TranscribeConfig

    t = _make_transcript("cached")
    cache = tmp_path / "transcript.json"
    cache.write_text(t.to_json(), encoding="utf-8")

    # mp4 path doesn't need to exist; we should load the cache
    result = transcribe(
        tmp_path / "cached.mp4",
        "cached",
        TranscribeConfig(),
        out_path=cache,
        overwrite=False,
    )
    assert result.video_id == "cached"
    assert len(result.segments) == 2


# ── _merge_segments ───────────────────────────────────────────────────────────


def _seg(start: float, end: float, text: str = "x") -> Segment:
    return Segment(start=start, end=end, text=text, words=[])


def test_merge_segments_no_overlap():
    chunk0 = [_seg(0.0, 5.0), _seg(5.0, 10.0)]
    chunk1 = [_seg(30.0, 35.0), _seg(35.0, 40.0)]
    merged = _merge_segments([chunk0, chunk1], chunk_starts=[0.0, 30.0])
    assert len(merged) == 4
    assert merged[0].start == 0.0
    assert merged[-1].start == 35.0


def test_merge_segments_drops_overlap_from_chunk1():
    # chunk0 covers 0-60s; chunk1 starts at 30s (overlap zone 30-60s)
    # segments from chunk1 with start < 30 should be dropped
    chunk0 = [_seg(0.0, 5.0), _seg(20.0, 25.0)]
    chunk1 = [_seg(25.0, 28.0, "dup"), _seg(30.0, 35.0, "new"), _seg(40.0, 45.0, "also new")]
    merged = _merge_segments([chunk0, chunk1], chunk_starts=[0.0, 30.0])
    texts = [s.text for s in merged]
    assert "dup" not in texts
    assert "new" in texts
    assert "also new" in texts


def test_merge_segments_sorted_by_start():
    chunk0 = [_seg(10.0, 12.0), _seg(0.0, 5.0)]
    chunk1 = [_seg(60.0, 65.0), _seg(50.0, 55.0)]
    merged = _merge_segments([chunk0, chunk1], chunk_starts=[0.0, 50.0])
    starts = [s.start for s in merged]
    assert starts == sorted(starts)


def test_merge_segments_single_chunk():
    chunk0 = [_seg(0.0, 5.0), _seg(5.0, 10.0)]
    merged = _merge_segments([chunk0], chunk_starts=[0.0])
    assert len(merged) == 2


def test_merge_segments_empty_chunk():
    chunk0 = [_seg(0.0, 5.0)]
    merged = _merge_segments([chunk0, []], chunk_starts=[0.0, 30.0])
    assert len(merged) == 1


# ── _extract_audio_chunk ──────────────────────────────────────────────────────


def test_extract_audio_chunk_calls_ffmpeg(tmp_path):
    mp4 = tmp_path / "video.mp4"
    mp4.touch()
    out_wav = tmp_path / "chunk.wav"
    with patch("clipsmith.transcribe.subprocess.check_call") as mock_cc:
        _extract_audio_chunk(mp4, start_s=60.0, duration_s=1830.0, out_wav=out_wav)
    args = mock_cc.call_args[0][0]
    assert "ffmpeg" in args[0]
    assert "60.0" in args
    assert "1830.0" in args
    assert str(out_wav) in args
    assert "-ar" in args and "16000" in args
    assert "-ac" in args and "1" in args
