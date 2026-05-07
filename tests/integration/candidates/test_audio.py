"""Integration tests for audio RMS series extraction (subprocess mocked)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from clipsmith.candidates.audio import compute_audio_rms_series


def _fake_ametadata(*entries: tuple[float, float]) -> str:
    lines: list[str] = []
    for pts, db in entries:
        lines.append(f"frame:0   pts:0       pts_time:{pts}")
        lines.append(f"lavfi.astats.Overall.RMS_level={db}")
    return "\n".join(lines)


def test_rms_series_parses_ffmpeg_output(tmp_path: Path) -> None:
    fake_output = _fake_ametadata((0.0, -20.5), (2.0, -18.3), (4.0, -22.1))
    mp4 = tmp_path / "video.mp4"
    mp4.touch()

    mock_result = MagicMock()
    mock_result.stdout = fake_output

    with patch("clipsmith.candidates.audio.subprocess.run", return_value=mock_result):
        series = compute_audio_rms_series(mp4, window_s=2.0)

    assert len(series) == 3
    times = [t for t, _ in series]
    assert times[0] == 1.0  # 0.0 + window_s/2
    assert times[1] == 3.0
    assert times[2] == 5.0


def test_rms_series_skips_silence(tmp_path: Path) -> None:
    fake_output = _fake_ametadata((0.0, -91.0), (2.0, -20.0), (4.0, -90.5))
    mp4 = tmp_path / "video.mp4"
    mp4.touch()

    mock_result = MagicMock()
    mock_result.stdout = fake_output

    with patch("clipsmith.candidates.audio.subprocess.run", return_value=mock_result):
        series = compute_audio_rms_series(mp4, window_s=2.0)

    assert len(series) == 1
    assert series[0][1] == -20.0
