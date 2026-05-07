"""Unit tests for transcription.transcriber — cache loading and segment merging."""

from __future__ import annotations

from clipsmith.models.transcript import Segment, Transcript, Word
from clipsmith.transcription.transcriber import _merge_segments


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


def _seg(start: float, end: float, text: str = "x") -> Segment:
    return Segment(start=start, end=end, text=text, words=[])


def test_transcribe_loads_from_cache(tmp_path) -> None:
    from clipsmith.settings import TranscribeConfig
    from clipsmith.transcription.transcriber import transcribe

    t = _make_transcript("cached")
    cache = tmp_path / "transcript.json"
    cache.write_text(t.to_json(), encoding="utf-8")

    result = transcribe(
        tmp_path / "cached.mp4",
        "cached",
        TranscribeConfig(),
        out_path=cache,
        overwrite=False,
    )
    assert result.video_id == "cached"
    assert len(result.segments) == 2


def test_merge_segments_no_overlap() -> None:
    chunk0 = [_seg(0.0, 5.0), _seg(5.0, 10.0)]
    chunk1 = [_seg(30.0, 35.0), _seg(35.0, 40.0)]
    merged = _merge_segments([chunk0, chunk1], chunk_starts=[0.0, 30.0])
    assert len(merged) == 4
    assert merged[0].start == 0.0
    assert merged[-1].start == 35.0


def test_merge_segments_drops_overlap_from_chunk1() -> None:
    chunk0 = [_seg(0.0, 5.0), _seg(20.0, 25.0)]
    chunk1 = [_seg(25.0, 28.0, "dup"), _seg(30.0, 35.0, "new"), _seg(40.0, 45.0, "also new")]
    merged = _merge_segments([chunk0, chunk1], chunk_starts=[0.0, 30.0])
    texts = [s.text for s in merged]
    assert "dup" not in texts
    assert "new" in texts
    assert "also new" in texts


def test_merge_segments_sorted_by_start() -> None:
    chunk0 = [_seg(10.0, 12.0), _seg(0.0, 5.0)]
    chunk1 = [_seg(60.0, 65.0), _seg(50.0, 55.0)]
    merged = _merge_segments([chunk0, chunk1], chunk_starts=[0.0, 50.0])
    starts = [s.start for s in merged]
    assert starts == sorted(starts)


def test_merge_segments_single_chunk() -> None:
    chunk0 = [_seg(0.0, 5.0), _seg(5.0, 10.0)]
    merged = _merge_segments([chunk0], chunk_starts=[0.0])
    assert len(merged) == 2


def test_merge_segments_empty_chunk() -> None:
    chunk0 = [_seg(0.0, 5.0)]
    merged = _merge_segments([chunk0, []], chunk_starts=[0.0, 30.0])
    assert len(merged) == 1
