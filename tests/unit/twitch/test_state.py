"""Tests for twitch.state — JSON persistence."""

from __future__ import annotations

from clipsmith.twitch.state import State


def test_state_persists_across_instances(tmp_path):
    p = tmp_path / "state.json"
    s1 = State(p)
    assert s1.seen == set()
    s1.mark_seen("v1")
    s1.mark_seen("v2")
    s1.mark_seen("v1")  # idempotent

    s2 = State(p)
    assert s2.seen == {"v1", "v2"}


def test_state_recovers_from_corrupt_file(tmp_path):
    p = tmp_path / "state.json"
    p.write_text("not json{", encoding="utf-8")
    s = State(p)
    assert s.seen == set()
    s.mark_seen("v1")
    assert State(p).seen == {"v1"}
