"""Sliding-window chat density scoring, separated for testability."""

from __future__ import annotations

from .chat import ChatMessage


def compute_density_scores(
    messages: list[ChatMessage],
    *,
    window_s: float = 15.0,
    peak_multiplier: float = 4.0,
    step_s: float = 5.0,
) -> list[tuple[float, float]]:
    """Return (t_center, score) for windows that exceed peak_multiplier × baseline.

    Score = messages_in_window + 0.5 × hype_emotes_in_window, normalised by
    baseline, so higher-than-baseline windows get a proportional score boost.
    """
    if not messages:
        return []

    times = [m.time_in_seconds for m in messages]
    t_min, t_max = min(times), max(times)
    total_duration = max(t_max - t_min, 1.0)

    # Baseline: average messages per window_s across the whole VOD.
    baseline = len(messages) * window_s / total_duration

    if baseline < 1.0:
        baseline = 1.0  # avoid div-by-zero for very sparse chats

    results: list[tuple[float, float]] = []
    t = t_min
    while t <= t_max:
        window_msgs = [
            m for m in messages if t <= m.time_in_seconds < t + window_s
        ]
        count = len(window_msgs)
        hype = sum(m.hype_emote_count for m in window_msgs)
        raw_score = count + 0.5 * hype
        ratio = raw_score / baseline

        if ratio >= peak_multiplier:
            center = t + window_s / 2
            results.append((center, raw_score))

        t += step_s

    return results
