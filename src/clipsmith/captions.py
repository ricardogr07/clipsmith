"""ASS subtitle generation for burned-in karaoke captions."""

from __future__ import annotations

from pathlib import Path

from .models.transcript import Transcript, Word
from .settings import CaptionConfig

_WORDS_PER_LINE = 5
_MAX_LINE_CHARS = 28


def _write_ass(
    transcript: Transcript,
    clip_start: float,
    clip_end: float,
    config: CaptionConfig,
    out_path: Path,
) -> None:
    lines = _caption_lines(transcript, clip_start, clip_end)
    out_path.write_text(_render_ass(lines, config), encoding="utf-8-sig")


def _caption_lines(
    transcript: Transcript,
    clip_start: float,
    clip_end: float,
) -> list[tuple[float, float, str]]:
    """Return (rel_start, rel_end, ass_text) tuples for the clip range."""
    words: list[Word] = []
    for seg in transcript.segments:
        if seg.end < clip_start or seg.start > clip_end:
            continue
        for w in seg.words:
            if clip_start <= w.start and w.end <= clip_end + 0.5:
                words.append(w)

    if words:
        return _group_words(words, clip_start)
    return _fallback_segments(transcript, clip_start, clip_end)


def _group_words(words: list[Word], clip_start: float) -> list[tuple[float, float, str]]:
    groups: list[tuple[float, float, str]] = []
    chunk: list[Word] = []

    for w in words:
        chunk.append(w)
        if len(chunk) >= _WORDS_PER_LINE or len(_chunk_text(chunk)) >= _MAX_LINE_CHARS:
            groups.append(_make_karaoke_line(chunk, clip_start))
            chunk = []

    if chunk:
        groups.append(_make_karaoke_line(chunk, clip_start))
    return groups


def _make_karaoke_line(words: list[Word], clip_start: float) -> tuple[float, float, str]:
    rel_start = max(0.0, words[0].start - clip_start)
    rel_end = max(rel_start + 0.1, words[-1].end - clip_start)
    parts = [f"{{\\kf{max(1, round((w.end - w.start) * 100))}}}{w.word.strip()}" for w in words]
    return rel_start, rel_end, " ".join(parts)


def _chunk_text(words: list[Word]) -> str:
    return " ".join(w.word.strip() for w in words)


def _fallback_segments(
    transcript: Transcript,
    clip_start: float,
    clip_end: float,
) -> list[tuple[float, float, str]]:
    """Segment-level captions when word timestamps are absent."""
    lines: list[tuple[float, float, str]] = []
    for seg in transcript.segments:
        if seg.end < clip_start or seg.start > clip_end:
            continue
        rel_start = max(0.0, seg.start - clip_start)
        rel_end = seg.end - clip_start
        seg_words = seg.text.strip().split()
        n = len(seg_words)
        if not n:
            continue
        for i in range(0, n, _WORDS_PER_LINE):
            chunk = seg_words[i : i + _WORDS_PER_LINE]
            t0 = rel_start + (i / n) * (rel_end - rel_start)
            t1 = rel_start + (min(i + _WORDS_PER_LINE, n) / n) * (rel_end - rel_start)
            lines.append((t0, t1, " ".join(chunk)))
    return lines


def _ass_time(seconds: float) -> str:
    """Seconds → ASS timestamp H:MM:SS.cc"""
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = min(99, round((seconds % 1) * 100))
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _alignment(position: str) -> int:
    """Map position name to ASS numpad alignment code."""
    return {"top": 8, "middle": 5}.get(position, 2)  # default: bottom-center


def _render_ass(lines: list[tuple[float, float, str]], config: CaptionConfig) -> str:
    header = (
        "[Script Info]\n"
        "Title: clipsmith\n"
        "ScriptType: v4.00+\n"
        "WrapStyle: 1\n"
        "ScaledBorderAndShadow: yes\n"
        "PlayResX: 1080\n"
        "PlayResY: 1920\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{config.font},{config.font_size},"
        "&H00FFFFFF,&H000000FF,&H00000000,&HA0000000,"
        f"1,0,0,0,100,100,0,0,1,{config.outline},0,"
        f"{_alignment(config.position)},20,20,80,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    events = "\n".join(
        f"Dialogue: 0,{_ass_time(s)},{_ass_time(e)},Default,,0,0,0,,{t}" for s, e, t in lines
    )
    return header + events + "\n"
