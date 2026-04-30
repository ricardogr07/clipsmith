"""Tests for downloader.py."""

from __future__ import annotations

from pathlib import Path


from clipsmith.downloader import download_vod, DownloadResult


def test_skip_download_if_file_exists(tmp_path):
    """Should not call twitch-dl if the MP4 already exists."""
    video_id = "v123"
    vod_dir = tmp_path / video_id
    vod_dir.mkdir()
    mp4 = vod_dir / f"{video_id}.mp4"
    mp4.write_bytes(b"\x00" * 100)  # fake mp4

    result = download_vod(video_id, tmp_path, overwrite=False)
    assert isinstance(result, DownloadResult)
    assert result.mp4_path == mp4


def test_creates_vod_dir(tmp_path, monkeypatch):
    """Should create work_dir/video_id/ and invoke twitch-dl."""
    calls: list[list[str]] = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        # Simulate twitch-dl creating the file
        Path(cmd[cmd.index("--output") + 1]).write_bytes(b"\x00")
        class R:
            returncode = 0
        return R()

    import subprocess
    monkeypatch.setattr(subprocess, "run", fake_run)

    video_id = "v999"
    result = download_vod(video_id, tmp_path)
    assert result.video_id == video_id
    assert result.mp4_path.parent == tmp_path / video_id
    assert len(calls) == 1
    assert "twitch-dl" in calls[0][0]
    assert video_id in calls[0]
