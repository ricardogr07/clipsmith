"""Unit tests for audio RMS energy extraction and peak detection."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from clipsmith.audio_signal import compute_audio_rms_series, find_rms_peaks


def _fake_ametadata(*entries: tuple[float, float]) -> str:
    """Build synthetic ametadata output for given (pts_time, rms_db) pairs."""
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

    with patch("clipsmith.audio_signal.subprocess.run", return_value=mock_result):
        series = compute_audio_rms_series(mp4, window_s=2.0)

    assert len(series) == 3
    times = [t for t, _ in series]
    # pts_time is window start; t_center = pts_time + window_s / 2
    assert times[0] == 1.0  # 0.0 + 1.0
    assert times[1] == 3.0  # 2.0 + 1.0
    assert times[2] == 5.0  # 4.0 + 1.0


def test_rms_series_skips_silence(tmp_path: Path) -> None:
    fake_output = _fake_ametadata((0.0, -91.0), (2.0, -20.0), (4.0, -90.5))
    mp4 = tmp_path / "video.mp4"
    mp4.touch()

    mock_result = MagicMock()
    mock_result.stdout = fake_output

    with patch("clipsmith.audio_signal.subprocess.run", return_value=mock_result):
        series = compute_audio_rms_series(mp4, window_s=2.0)

    # Only the -20.0 dB window survives; the two silence windows are filtered
    assert len(series) == 1
    assert series[0][1] == -20.0


def test_rms_peaks_detects_spike() -> None:
    # 9 windows at -20 dB, 1 window at -10 dB (clear spike)
    series = [(float(i), -20.0) for i in range(9)]
    series.append((9.0, -10.0))

    peaks = find_rms_peaks(series, peak_multiplier=2.0)

    assert len(peaks) == 1
    t, score = peaks[0]
    assert t == 9.0
    assert score > 0


def test_rms_peaks_flat_signal_no_peaks() -> None:
    # All windows at the same dB → std ≈ 0 → no peaks
    series = [(float(i), -20.0) for i in range(20)]

    peaks = find_rms_peaks(series, peak_multiplier=2.0)

    assert peaks == []
