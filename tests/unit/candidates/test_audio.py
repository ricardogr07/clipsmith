"""Unit tests for audio RMS peak detection (pure math, no subprocess)."""

from __future__ import annotations

from clipsmith.candidates.audio import find_rms_peaks


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
