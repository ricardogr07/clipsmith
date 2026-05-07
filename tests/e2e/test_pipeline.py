"""End-to-end pipeline tests.

These tests require:
- Real credentials in .env (TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET, ANTHROPIC_API_KEY)
- ffmpeg on PATH
- A short publicly-accessible Twitch VOD ID in the E2E_VOD_ID environment variable

Run explicitly with:
    pytest tests/e2e/ --run-e2e
Or set E2E_VOD_ID and pass --run-e2e to CI.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from clipsmith.models.twitch import Video
from clipsmith.pipeline import process_vod
from clipsmith.settings import load_config, load_secrets


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def vod_id() -> str:
    vid = os.environ.get("E2E_VOD_ID", "")
    if not vid:
        pytest.skip("E2E_VOD_ID not set — skipping e2e tests")
    return vid


@pytest.fixture(scope="module")
def cfg():
    return load_config(Path(__file__).parents[2] / "config.yaml")


@pytest.fixture(scope="module")
def secrets():
    return load_secrets()


@pytest.fixture(scope="module")
def video(vod_id: str) -> Video:
    return Video(
        id=vod_id,
        user_id="",
        user_login="e2e_test",
        title="E2E Test VOD",
        duration="5m0s",
        type="archive",
        url=f"https://www.twitch.tv/videos/{vod_id}",
        created_at="2026-01-01T00:00:00Z",
        thumbnail_url="",
        view_count=0,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_pipeline_download_only(video, cfg, secrets, tmp_path) -> None:
    """Download a short VOD; skip all subsequent stages."""
    cfg.work_dir = tmp_path
    process_vod(
        video,
        cfg,
        secrets,
        skip_transcribe=True,
        skip_chat=True,
        skip_select=True,
        skip_clip=True,
    )
    mp4 = tmp_path / video.id / f"{video.id}.mp4"
    assert mp4.exists(), f"Expected downloaded MP4 at {mp4}"
    assert mp4.stat().st_size > 0


def test_pipeline_transcribe(video, cfg, secrets, tmp_path) -> None:
    """Download + transcribe; skip LLM selection and clipping."""
    cfg.work_dir = tmp_path
    process_vod(
        video,
        cfg,
        secrets,
        skip_chat=True,
        skip_select=True,
        skip_clip=True,
    )
    transcript_json = tmp_path / video.id / "transcript.json"
    assert transcript_json.exists()
    data = json.loads(transcript_json.read_text(encoding="utf-8"))
    assert "segments" in data
    assert isinstance(data["segments"], list)


def test_pipeline_candidates(video, cfg, secrets, tmp_path) -> None:
    """Download + transcribe + chat + candidate scoring; skip LLM + clipping."""
    cfg.work_dir = tmp_path
    process_vod(
        video,
        cfg,
        secrets,
        skip_select=True,
        skip_clip=True,
    )
    candidates_json = tmp_path / video.id / "candidates.json"
    assert candidates_json.exists()


def test_pipeline_full(video, cfg, secrets, tmp_path) -> None:
    """Full pipeline: download → transcribe → candidates → LLM selection → clip.

    Makes real API calls to the configured LLM provider and runs ffmpeg.
    """
    cfg.work_dir = tmp_path
    out_dir = tmp_path / "out"
    cfg.out_dir = out_dir

    process_vod(video, cfg, secrets)

    picks_json = tmp_path / video.id / "picks.json"
    assert picks_json.exists()
    picks = json.loads(picks_json.read_text(encoding="utf-8"))
    assert isinstance(picks, list)
    if picks:
        clip_dir = out_dir / video.id
        assert clip_dir.exists()
