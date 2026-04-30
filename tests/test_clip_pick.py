"""Tests for ClipPick parsing and duration clamping."""

from __future__ import annotations

import json

import pytest

from clipsmith.llm.base import ClipPick
from clipsmith.selector import _clamp_duration
from clipsmith.settings import ClipConfig


def _cfg(**kwargs: object) -> ClipConfig:
    defaults: dict[str, object] = {"min_seconds": 15, "max_seconds": 30, "preroll_s": 25, "postroll_s": 10}
    defaults.update(kwargs)
    return ClipConfig(**defaults)  # type: ignore[arg-type]


# ── ClipPick parsing ──────────────────────────────────────────────────────────

def test_clip_pick_from_json_plain() -> None:
    raw = json.dumps({
        "include": True,
        "start_offset_s": 290.0,
        "end_offset_s": 318.0,
        "title_es": "Reacción épica",
        "reason": "Huge chat spike, very funny moment.",
    })
    pick = ClipPick.from_json(raw)
    assert pick.include is True
    assert pick.start_offset_s == pytest.approx(290.0)
    assert pick.end_offset_s == pytest.approx(318.0)
    assert pick.title_es == "Reacción épica"


def test_clip_pick_from_json_strips_markdown_fences() -> None:
    raw = "```json\n{\"include\":false,\"start_offset_s\":0,\"end_offset_s\":0,\"title_es\":\"n/a\",\"reason\":\"not funny\"}\n```"
    pick = ClipPick.from_json(raw)
    assert pick.include is False


def test_clip_pick_duration() -> None:
    pick = ClipPick(include=True, start_offset_s=100.0, end_offset_s=125.0, title_es="t", reason="r")
    assert pick.duration_s == pytest.approx(25.0)


def test_clip_pick_roundtrip() -> None:
    original = ClipPick(include=True, start_offset_s=50.0, end_offset_s=78.5, title_es="Momento", reason="good")
    restored = ClipPick.from_dict(original.to_dict())
    assert restored.include == original.include
    assert restored.start_offset_s == pytest.approx(original.start_offset_s)
    assert restored.title_es == original.title_es


# ── duration clamping ─────────────────────────────────────────────────────────

def test_clamp_too_short_extends_end() -> None:
    pick = ClipPick(include=True, start_offset_s=100.0, end_offset_s=109.0, title_es="t", reason="r")
    clamped = _clamp_duration(pick, _cfg(min_seconds=15, max_seconds=30))
    assert clamped.end_offset_s == pytest.approx(115.0)


def test_clamp_too_long_trims_end() -> None:
    pick = ClipPick(include=True, start_offset_s=100.0, end_offset_s=145.0, title_es="t", reason="r")
    clamped = _clamp_duration(pick, _cfg(min_seconds=15, max_seconds=30))
    assert clamped.end_offset_s == pytest.approx(130.0)


def test_clamp_ok_unchanged() -> None:
    pick = ClipPick(include=True, start_offset_s=100.0, end_offset_s=120.0, title_es="t", reason="r")
    clamped = _clamp_duration(pick, _cfg(min_seconds=15, max_seconds=30))
    assert clamped.end_offset_s == pytest.approx(120.0)
