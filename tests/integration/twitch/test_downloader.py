"""Integration tests for twitch.downloader — subprocess mocked."""

from __future__ import annotations

from pathlib import Path

from clipsmith.twitch.downloader import DownloadResult, download_vod


def test_skip_download_if_file_exists(tmp_path) -> None:
    video_id = "v123"
    vod_dir = tmp_path / video_id
    vod_dir.mkdir()
    mp4 = vod_dir / f"{video_id}.mp4"
    mp4.write_bytes(b"\x00" * 100)

    result = download_vod(video_id, tmp_path, overwrite=False)
    assert isinstance(result, DownloadResult)
    assert result.mp4_path == mp4


def test_creates_vod_dir(tmp_path, monkeypatch) -> None:
    download_calls: list[list[str]] = []

    def fake_run(cmd, **kw):
        if "info" in cmd:

            class InfoR:
                stdout = "1080p60"
                stderr = ""
                returncode = 0

            return InfoR()
        download_calls.append(cmd)
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
    assert len(download_calls) == 1
    assert "twitchdl" in " ".join(download_calls[0])
    assert video_id in download_calls[0]
