"""Integration tests for transcription.transcriber — subprocess calls (mocked)."""

from __future__ import annotations

from unittest.mock import patch

from clipsmith.transcription.transcriber import _extract_audio_chunk


def test_extract_audio_chunk_calls_ffmpeg(tmp_path) -> None:
    mp4 = tmp_path / "video.mp4"
    mp4.touch()
    out_wav = tmp_path / "chunk.wav"
    with patch("clipsmith.transcription.transcriber.subprocess.check_call") as mock_cc:
        _extract_audio_chunk(mp4, start_s=60.0, duration_s=1830.0, out_wav=out_wav)
    args = mock_cc.call_args[0][0]
    assert "ffmpeg" in args[0]
    assert "60.0" in args
    assert "1830.0" in args
    assert str(out_wav) in args
    assert "-ar" in args and "16000" in args
    assert "-ac" in args and "1" in args
